# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Autopiloot is a production-ready 8-agent system built with Agency Swarm v1.0.2 for automated YouTube content processing and strategic content analysis. The system discovers videos, transcribes them via AssemblyAI, generates business-focused summaries, analyzes content strategy through LinkedIn data, manages Google Drive documentation, and provides comprehensive operational monitoring with strict cost controls.

**Core Architecture**: Event-driven broker pattern where Firestore serves as both data store and event broker, with Firebase Functions v2 for scheduling and automation.

## Common Development Commands

### Testing

```bash
# Run all tests (160+ comprehensive tests across 8 agents)
cd autopiloot
python -m unittest discover tests -v

# Test specific modules
python -m unittest tests.test_config -v                    # Configuration tests (11 cases)
python -m unittest tests.test_env_loader -v                # Environment validation (17 cases)
python -m unittest tests.test_audit_logger -v              # Audit logging (15 cases)
python -m unittest tests.test_reliability -v               # Error handling (22 cases)
python -m unittest tests.test_sheets -v                    # Google Sheets integration (18 cases)

# Observability agent tests (11/11 tools, 95+ tests)
python -m unittest tests.observability_tools.test_send_error_alert -v
python -m unittest tests.observability_tools.test_monitor_transcription_budget -v
python -m unittest tests.observability_tools.test_generate_daily_digest -v
python -m unittest tests.observability_tools.test_alert_engine -v

# Orchestrator agent tests (8/8 tools, 120+ tests)
python -m unittest tests.orchestrator_tools.test_dispatch_scraper -v
python -m unittest tests.orchestrator_tools.test_enforce_policies -v
python -m unittest tests.orchestrator_tools.test_plan_daily_run -v

# Transcriber agent tests (5/5 tools, 56+ tests)
python -m unittest tests.test_get_video_audio_url -v
python -m unittest tests.test_submit_assemblyai_job -v
python -m unittest tests.test_poll_transcription_job -v
python -m unittest tests.test_store_transcript_to_drive -v
python -m unittest tests.test_save_transcript_record -v

# Summarizer agent tests (7/7 tools, 47+ tests)
python -m unittest tests.test_generate_short_summary -v
python -m unittest tests.test_store_short_in_zep -v
python -m unittest tests.test_save_summary_record_enhanced -v

# Drive agent tests (8/8 tools with 100% coverage)
python -m unittest tests.drive_tools.test_drive_agent -v
python -m unittest tests.drive_tools.test_extract_text_from_document -v
python -m unittest tests.drive_tools.test_upsert_drive_docs_to_zep -v

# LinkedIn agent tests (10/10 tools, strategic analysis)
python -m unittest tests.linkedin_tools.test_compute_linkedin_stats -v
python -m unittest tests.linkedin_tools.test_get_user_posts -v
python -m unittest tests.linkedin_tools.test_normalize_linkedin_content -v

# Strategy agent tests (9/9 tools, content strategy analysis)
python -m unittest tests.strategy_tools.test_classify_post_types -v
python -m unittest tests.strategy_tools.test_generate_content_briefs -v
python -m unittest tests.strategy_tools.test_cluster_topics_embeddings -v

# Test individual tools (each has test block)
python scraper_agent/tools/save_video_metadata.py
python transcriber_agent/tools/poll_transcription_job.py
python summarizer_agent/tools/generate_short_summary.py
python observability_agent/tools/send_error_alert.py

# Validate environment setup
python config/env_loader.py
```

### Code Quality

```bash
# Lint with ruff (follows pyproject.toml configuration)
cd autopiloot
ruff check . --output-format=github
ruff format --check .

# Type checking with mypy
mypy --config-file=pyproject.toml .

# Security scanning
bandit -r . -f txt
safety check

# Check tool naming convention (snake_case enforcement)
./scripts/check_tool_filenames_snake_case.sh
```

### Agency Operations

```bash
# Run the agency (requires .env configuration)
cd autopiloot
python agency.py

# Deploy Firebase Functions
firebase deploy --only functions

# Test Firebase Functions locally
firebase emulators:start --only functions,firestore
```

### Development Setup

```bash
# Environment setup
cd autopiloot
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment (REQUIRED)
cp .env.template .env
# Edit .env with actual API keys (see docs/environment.md)

# Validate configuration
python config/env_loader.py
```

## High-Level Architecture

### Agency Swarm v1.0.2 Framework

- **Framework Compliance**: All tools inherit from `agency_swarm.tools.BaseTool` with Pydantic Field validation
- **Return Convention**: All tool `run()` methods return JSON strings (not Dict objects)
- **Agent Structure**: 8 production agents in `{agent_name}/` directories with `tools/` subdirectories
- **Communication Flow**: OrchestratorAgent (CEO) coordinates all agents; core pipeline ScraperAgent → TranscriberAgent → SummarizerAgent; parallel analysis via DriveAgent, LinkedinAgent, StrategyAgent; ObservabilityAgent monitors all
- **Tool Count**: 86 production tools across all agents (all using snake_case filenames)

### Multi-Layer Configuration System

1. **Environment Variables** (`.env`): API keys, credentials, secrets
2. **settings.yaml**: Business rules, thresholds, operational parameters, LLM configurations
3. **agency_manifesto.md**: Shared operational standards across all agents
4. **Agent instructions.md**: Agent-specific workflows and guidelines

### Firestore as Event Broker

- **Core Pattern**: All data mutations flow through Firestore exclusively
- **Collections**: `videos/`, `transcripts/`, `summaries/`, `jobs/transcription/`, `costs_daily/`, `audit_logs/`, `jobs_deadletter/`, `alert_throttling/`
- **Status Progression**: `discovered` → `transcription_queued` → `transcribed` → `summarized`
- **Idempotency**: Document IDs use YouTube video_id as natural key
- **Audit Trail**: All key actions logged to `audit_logs` collection (TASK-AUDIT-0041 compliance)

### Reliability & Error Handling

- **Dead Letter Queue**: Failed operations route to `jobs_deadletter` collection after 3 retries
- **Exponential Backoff**: 60s → 120s → 240s retry delays
- **Quota Management**: YouTube API (10k units/day), AssemblyAI ($5/day budget with 80% threshold alerts)
- **Checkpoint System**: `lastPublishedAt` persistence for incremental processing
- **Alert Throttling**: 1-alert-per-type-per-hour to prevent notification spam

### Firebase Functions Integration

- **Scheduled Execution**: Daily scraping at 01:00 Europe/Amsterdam via Cloud Scheduler
- **Event-Driven**: Budget monitoring triggered by Firestore document writes
- **Daily Digest**: Automated 07:00 Europe/Amsterdam Slack digest with processing summary, costs, and system health
- **Deployment**: Manual via Firebase CLI with service account authentication
- **Configuration**: Functions import agency classes directly, reuse environment config

## Critical Implementation Details

### Tool Development Standards

- **NEVER** include API keys as tool parameters - always use environment variables via `config/env_loader.py`
- **ALWAYS** validate required environment variables in tool initialization
- **ALWAYS** include test block with `if __name__ == "__main__":` in every tool
- **ALWAYS** use JSON string returns from `run()` methods (not Dict objects)
- **File Naming**: Tools use snake_case filenames (enforced by CI pipeline)
- **Class Naming**: Tool classes use PascalCase matching the file content

### Agent Communication Pattern

```python
# Agency chart defines allowed communication flows (8-agent architecture)
agency_chart = [
    orchestrator_agent,  # CEO can communicate with all
    [orchestrator_agent, scraper_agent],     # Workflow dispatch
    [orchestrator_agent, transcriber_agent], # Workflow dispatch
    [orchestrator_agent, summarizer_agent],  # Workflow dispatch
    [orchestrator_agent, drive_agent],       # Document management
    [orchestrator_agent, linkedin_agent],    # LinkedIn data ingestion
    [orchestrator_agent, strategy_agent],    # Content strategy analysis
    [scraper_agent, transcriber_agent],      # Core pipeline
    [transcriber_agent, summarizer_agent],   # Processing pipeline
    [linkedin_agent, strategy_agent],        # Strategic analysis flow
    [drive_agent, strategy_agent],           # Documentation and strategy
    [observability_agent, orchestrator_agent], # Monitoring flows
    [observability_agent, scraper_agent, transcriber_agent, summarizer_agent,
     drive_agent, linkedin_agent, strategy_agent], # Multi-directional monitoring
]
```

### Business Rule Enforcement

- **Duration Limit**: 70 minutes (4200 seconds) maximum video duration
- **Daily Limits**: 10 videos per channel, $5 transcription budget
- **Archive-First**: Google Sheets rows archived before deletion for audit trail
- **Quota Handling**: Graceful degradation when YouTube/AssemblyAI quotas exhausted
- **Idempotent Operations**: All tools designed for safe retry without side effects

### Error Response Format

All tools return consistent JSON error structures:

```python
{
    "error": "error_type",
    "message": "Human-readable description",
    "details": {...}  # Optional additional context
}
```

## Configuration Architecture

### Runtime Settings (`config/settings.yaml`)

```yaml
# Content discovery
sheet: "1AbC2defGhIJkLmNoPqRSTuVwxyz0123456789"
scraper:
  handles: ["@AlexHormozi"]
  daily_limit_per_channel: 10

# LLM configuration with task-specific overrides
llm:
  default:
    model: "gpt-4.1"
    temperature: 0.2
  tasks:
    summarizer_generate_short:
      model: "gpt-4.1"
      temperature: 0.2
      max_output_tokens: 1500
      prompt_version: "v1"

# Operational settings
notifications:
  slack:
    channel: "ops-autopiloot"
    digest:
      enabled: true
      time: "07:00"
      timezone: "Europe/Amsterdam"
      channel: "ops-autopiloot"

budgets:
  transcription_daily_usd: 5.0

# Business rules
idempotency:
  max_video_duration_sec: 4200 # 70 minutes

# Reliability settings
reliability:
  max_retry_attempts: 3
  base_delay_seconds: 60
```

### Environment Variables (`.env`)

Critical environment variables (see `config/env_loader.py` for complete list):

```bash
# Core APIs
OPENAI_API_KEY=sk-...
ASSEMBLYAI_API_KEY=...
YOUTUBE_API_KEY=...
SLACK_BOT_TOKEN=xoxb-...

# Google Cloud
GCP_PROJECT_ID=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GOOGLE_DRIVE_FOLDER_ID_TRANSCRIPTS=...
GOOGLE_DRIVE_FOLDER_ID_SUMMARIES=...

# Optional integrations
ZEP_API_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_HOST=https://cloud.langfuse.com

# LinkedIn and Strategy Agent integrations
LINKEDIN_ACCESS_TOKEN=...
LINKEDIN_API_URL=https://api.linkedin.com/v2
```

## Testing Strategy

### Test Coverage (160+ Tests across 8 Agents)

- **Configuration**: 28 tests (config loading, environment validation)
- **Core Systems**: 22 tests (reliability, audit logging, idempotency)
- **Agent Tools**: 240+ tests across all 8 agent workflows
- **Drive Agent**: 100% test coverage for core initialization (18/18 lines)
- **LinkedIn Agent**: Strategic content analysis and ingestion testing
- **Strategy Agent**: NLP clustering, content classification, and brief generation
- **Edge Cases**: 75 additional boundary condition tests
- **Integration**: Firebase functions, API integrations, end-to-end workflows

### Test Categories

```
Unit Tests (isolated functionality)
├── test_config.py (11 tests) - YAML loading and validation
├── test_env_loader.py (17 tests) - Environment variable validation
├── test_audit_logger.py (15 tests) - Audit logging compliance
└── test_reliability.py (22 tests) - Error handling and retry logic

Integration Tests (API and service integration)
├── Orchestrator Pipeline (120+ tests across 8 tools)
├── Transcriber Pipeline (56+ tests across 5 tools)
├── Summarizer Workflows (47+ tests across 7 tools)
├── Observability Monitoring (95+ tests across 11 tools)
├── Scraper Discovery (35+ tests across 7 tools)
├── Drive Agent Tools (8 tools with 100% coverage)
├── LinkedIn Agent Pipeline (10 tools with strategic analysis)
└── Strategy Agent NLP (9 tools with content classification)

End-to-End Tests
├── Firebase Functions deployment and execution
├── Complete agent workflows with real API integration
└── Error recovery and dead letter queue scenarios
```

### Mock Strategy

- **External APIs**: Mock YouTube, AssemblyAI, OpenAI, Slack, Zep, LinkedIn clients
- **Google Services**: Mock Firestore, Drive API with in-memory storage
- **Agency Swarm**: Mock Agent and ModelSettings classes for dependency-free testing
- **Configuration**: Use test environment variables and mock credentials
- **Time-based**: Mock datetime for consistent testing of time-sensitive features
- **NLP Libraries**: Mock scikit-learn, NLTK for Strategy Agent testing

## Firebase Deployment

### Functions Structure

```
services/firebase/functions/
├── main.py          # Entry points for HTTP and scheduled functions
├── scheduler.py     # Scheduled functions (daily scraper, budget monitoring, digest)
├── core.py          # Shared utilities and agency integration
└── requirements.txt # Firebase-specific dependencies
```

### Deployment Commands

```bash
# Deploy all functions
firebase deploy --only functions

# Deploy specific function
firebase deploy --only functions:daily_scraper
firebase deploy --only functions:daily_digest

# Test locally with emulator
firebase emulators:start --only functions,firestore
```

### Function Types

- **Scheduled**: `daily_scraper` (01:00 CET), `daily_digest` (07:00 CET)
- **Event-driven**: `budget_monitor` (triggered by Firestore writes to `costs_daily/`)
- **HTTP**: Health checks and manual triggers for development

## Daily Digest System

### Features

- **Automated Delivery**: Every day at 07:00 Europe/Amsterdam timezone
- **Rich Formatting**: Slack Block Kit with sections for processing summary, costs, errors, and quick links
- **Configurable**: Channel, sections, and timezone settings via `config/settings.yaml`
- **Data Sources**: Aggregates from Firestore collections (`videos/`, `costs_daily/`, `jobs_deadletter/`)

### Sample Output

```
🌅 Daily Digest | 2025-09-15

📊 Processing Summary
• Videos Discovered: 8 (6 scrape, 2 sheet)
• Videos Transcribed: 7
• Videos Summarized: 6
• Success Rate: 87.5%

💰 Daily Costs
• Transcription: $3.45 / $5.00 (69%)
• Status: 🟢 Within budget

⚠️ Issues & Alerts
• 1 video in dead letter queue
• No critical errors detected

🔗 Resources
📁 Transcripts | 📁 Summaries | 📊 Firestore Console
```

## Common Troubleshooting

### Missing Environment Variables

- Check `.env` file exists and contains all variables from `.env.template`
- Run `python config/env_loader.py` to identify missing variables
- Ensure Google service account file exists at specified path

### Tool Import Errors

- Tool class name must match filename exactly (both snake_case)
- Tools must be in `{agent_name}/tools/` directory
- All tools must inherit from `agency_swarm.tools.BaseTool`
- Check imports use correct module paths

### Firestore Connection Issues

- Verify `GCP_PROJECT_ID` environment variable is set
- Check service account has Firestore Admin permissions
- Ensure `GOOGLE_APPLICATION_CREDENTIALS` points to valid JSON file
- Test connection with `python config/env_loader.py`

### Quota and Budget Issues

- **YouTube**: Check quota usage in Google Cloud Console, monitor with `monitor_quota_state.py`
- **AssemblyAI**: Monitor daily costs in `costs_daily` collection, $5 budget with 80% alerts
- **Dead Letter Queue**: Use `query_dlq.py` and `handle_dlq.py` tools for analysis and recovery

### Security Review Requirements

Every code change must pass:

1. **Automated Scanning**: SAST with zero CRITICAL findings, dependency vulnerabilities, secrets detection
2. **Manual Review**: Authentication/authorization logic, cryptographic implementations, database queries
3. **Security Checklist**: No hardcoded secrets, parameterized queries, input validation, HTTPS enforcement

## Project Status

- **Completion**: 90/90 planned tasks completed and archived
- **Production Status**: ✅ Production ready with comprehensive monitoring across 8 agents
- **Test Coverage**: 160+ comprehensive tests including 100% coverage for Drive Agent core
- **CI/CD**: GitHub Actions pipeline with multi-Python version support
- **Documentation**: Complete ADR system with 37+ architectural decisions
- **Security**: Comprehensive audit trail, PII avoidance, admin-only Firestore access

## File Structure Key Points

```
autopiloot/
├── orchestrator_agent/    # CEO pattern - coordinates all other agents
├── scraper_agent/         # Content discovery and metadata management
├── transcriber_agent/     # AssemblyAI integration and transcript processing
├── summarizer_agent/      # LLM-powered summarization and storage
├── drive_agent/           # Google Drive document management and Zep GraphRAG integration
├── linkedin_agent/        # LinkedIn data ingestion and social content analysis
├── strategy_agent/        # Content strategy analysis with NLP clustering and classification
├── observability_agent/   # Monitoring, alerting, and operational oversight
├── core/                  # Shared utilities (audit logging, reliability, etc.)
├── config/               # Configuration management and environment validation
├── services/firebase/    # Firebase Functions for scheduling and automation
├── tests/               # Comprehensive test suite (160+ tests across 8 agents)
├── planning/archive/    # Completed task specifications (90 archived)
├── coverage/                # Test coverage reports for all agents
│   └── drive_agent/         # Drive Agent 100% coverage reports
└── docs/               # Implementation documentation and guides
```

Tools use snake_case filenames enforced by CI pipeline, with classes using PascalCase names. All 8 agents follow Agency Swarm v1.0.2 patterns with proper inheritance and validation.