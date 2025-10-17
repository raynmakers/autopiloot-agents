# Autopiloot Agency

A production-ready AI agency built with Agency Swarm v1.0.2 for comprehensive content processing, knowledge management, and strategic analysis across YouTube, LinkedIn, and Google Drive.

## Overview

Autopiloot is a comprehensive multi-agent system that automates content discovery, processing, and strategic analysis across multiple platforms. The system processes YouTube videos, LinkedIn content, and Google Drive documents, transforming them into actionable insights for content creators, entrepreneurs, and business strategists.

### Target Users

- Entrepreneurs creating content primarily for LinkedIn
- Business coaches and consultants with 6-figure+ revenue
- Content creators looking to streamline research and insight generation

### Value Proposition

End-to-end automation of multi-platform content processing and strategic analysis:

- ✅ **YouTube Processing**: Daily video discovery, transcription, and coaching-focused summarization
- ✅ **LinkedIn Intelligence**: Content ingestion, engagement analysis, and strategy synthesis
- ✅ **Drive Knowledge Management**: Document processing, text extraction, and semantic indexing
- ✅ **Strategic Analysis**: NLP-powered content analysis, trend detection, and playbook generation
- ✅ **Unified Search**: Zep GraphRAG integration across all content sources
- ✅ **Production Operations**: Cost controls, audit trails, and comprehensive monitoring

## Architecture Overview

**Modular Event-Driven Architecture**: Firestore serves as both data store and event broker, with a fully modular agent system that supports dynamic composition, configurable communication flows, and extensible scheduling.

### 🔧 Modular Architecture Features

- **Config-Driven Agent Loading**: Enable/disable agents via `settings.yaml` without code changes
- **Dynamic Communication Flows**: Configure agent communication topology from configuration
- **Agent-Provided Schedules**: Agents can expose their own schedules and triggers for Firebase Functions
- **CLI Scaffold**: Generate complete agent structures in seconds with consistent patterns
- **Comprehensive Testing**: Automated tests for all modular components with 95%+ coverage

👉 **[Complete Modular Architecture Guide](docs/modular-architecture.md)**

### 🤖 8-Agent Architecture

#### OrchestratorAgent (CEO)

**Role**: End-to-end pipeline orchestration and policy enforcement

- Plans daily runs across all content sources (YouTube, LinkedIn, Drive)
- Dispatches to specialized agents based on content type and priority
- Enforces reliability policies (retry/backoff, checkpoints, DLQ)
- Emits run events to Firestore for comprehensive observability
- **8 tools**: dispatch_scraper, dispatch_summarizer, dispatch_transcriber, emit_run_events, enforce_policies, handle_dlq, plan_daily_run, query_dlq

#### ScraperAgent

**Role**: Content discovery and metadata management

- YouTube channel handle resolution and uploads discovery
- Google Sheets backfill processing
- Video metadata storage with business rule validation (70-min limit)
- Transcription job queue management
- **7 tools**: enqueue_transcription, extract_youtube_from_page, list_recent_uploads, read_sheet_links, remove_sheet_row, resolve_channel_handles, save_video_metadata

#### TranscriberAgent

**Role**: Audio processing and transcript generation

- AssemblyAI integration with exponential backoff polling
- Dual-format storage (JSON + TXT) to Google Drive
- Cost tracking and budget monitoring integration
- Firestore transcript metadata management
- **5 tools**: get_video_audio_url, poll_transcription_job, save_transcript_record, save_transcript_record, submit_assemblyai_job

#### SummarizerAgent

**Role**: Content analysis and insight generation

- GPT-4.1 powered coaching-focused summaries
- Zep GraphRAG storage for semantic search
- Multi-platform persistence (Firestore, Drive, Zep)
- Enhanced metadata and reference linking
- **6 tools**: generate_short_summary, process_summary_workflow, save_summary_record, save_summary_record_enhanced, store_short_in_zep, save_summary_record

#### ObservabilityAgent

**Role**: Operations monitoring and alerting

- **Daily Digest**: Automated 07:00 Europe/Amsterdam Slack digest with processing summary, costs, errors, and system health
- Real-time budget monitoring with 80% threshold alerts
- Slack notifications with 1-per-type-per-hour throttling
- Error alerting and operational health monitoring
- Rich Slack Block Kit formatting for notifications
- **11 tools**: alert_engine, format_slack_blocks, generate_daily_digest, llm_observability_metrics, monitor_dlq_trends, monitor_quota_state, monitor_transcription_budget, report_daily_summary, send_error_alert, send_slack_message, stuck_job_scanner

#### LinkedInAgent

**Role**: Professional content ingestion and engagement analysis

- RapidAPI LinkedIn integration for posts, comments, and reactions
- Multi-profile content processing with daily limits (25 items per profile)
- Content normalization and deduplication with multiple strategies
- Engagement metrics computation and trend analysis
- Zep GraphRAG integration for professional content search
- **9 tools**: get_user_posts, get_post_comments, get_post_reactions, get_user_comment_activity, normalize_linkedin_content, deduplicate_entities, compute_linkedin_stats, upsert_to_zep_group, save_ingestion_record

#### StrategyAgent

**Role**: Content analysis and strategic playbook synthesis

- Corpus retrieval from Zep GraphRAG across all content sources
- NLP-powered analysis: keyword extraction, topic clustering, sentiment analysis
- Engagement signal computation and trend detection
- Content classification and tone analysis
- Strategic playbook generation with actionable insights
- **10 tools**: fetch_corpus_from_zep, compute_engagement_signals, extract_keywords_and_phrases, cluster_topics_embeddings, classify_post_types, analyze_tone_of_voice, mine_trigger_phrases, generate_content_briefs, synthesize_strategy_playbook, save_strategy_artifacts

#### DriveAgent

**Role**: Document knowledge management and semantic indexing

- Google Drive integration with incremental change detection
- Multi-format text extraction (PDF, DOCX, HTML, CSV, plain text)
- Google Workspace export support (Docs → DOCX, Sheets → CSV)
- Document chunking and Zep GraphRAG indexing for semantic search
- Comprehensive audit logging with performance metrics
- **7 tools**: list_tracked_targets_from_config, resolve_folder_tree, list_drive_changes, fetch_file_content, extract_text_from_document, upsert_drive_docs_to_zep, save_drive_ingestion_record

## 📅 Daily Digest

The system provides automated daily operational summaries delivered to Slack every morning at **07:00 Europe/Amsterdam** timezone.

### Features

- **📊 Processing Summary**: Videos discovered, transcribed, and summarized with source breakdown
- **💰 Cost Analysis**: Daily transcription spend vs. budget with percentage usage
- **⚠️ Error Monitoring**: Dead letter queue alerts and system health indicators
- **🔗 Quick Links**: Direct access to Google Drive folders and system resources
- **🎯 Performance Metrics**: Success rates, processing times, and operational KPIs

### Sample Output

The digest appears in Slack with rich formatting and actionable insights:

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

### Configuration

Configure digest behavior in `config/settings.yaml`:

```yaml
notifications:
  slack:
    digest:
      enabled: true # Enable/disable digest
      time: "07:00" # Delivery time (fixed at deployment)
      timezone: "Europe/Amsterdam" # Timezone for date calculations
      channel: "ops-autopiloot" # Target Slack channel
      sections: # Customize digest sections
        - "summary"
        - "budgets"
        - "issues"
        - "links"
```

**Note**: The delivery time (07:00) and timezone are fixed at Firebase Functions deployment time. Runtime configuration allows customizing the target channel, content sections, and timezone for date calculations.

### Troubleshooting

| Issue                | Solution                                                            |
| -------------------- | ------------------------------------------------------------------- |
| Digest not delivered | Check Firebase Functions logs, verify SLACK_BOT_TOKEN               |
| Wrong channel        | Update `notifications.slack.digest.channel` in settings.yaml        |
| Missing data         | Verify Firestore permissions and collection structure               |
| Timezone issues      | Ensure `notifications.slack.digest.timezone` is valid IANA timezone |

## Project Structure

```
autopiloot/
├── agency.py                     # Main agency orchestration (8-agent architecture)
├── agency_manifesto.md           # Shared operational standards
├── orchestrator_agent/
│   ├── orchestrator_agent.py    # CEO agent - pipeline orchestration
│   ├── instructions.md          # Agent-specific workflows
│   └── tools/                   # 8 orchestration tools
│       ├── dispatch_scraper.py
│       ├── dispatch_summarizer.py
│       ├── dispatch_transcriber.py
│       ├── emit_run_events.py
│       ├── enforce_policies.py
│       ├── handle_dlq.py
│       ├── plan_daily_run.py
│       └── query_dlq.py
├── scraper_agent/
│   ├── scraper_agent.py         # YouTube content discovery
│   ├── instructions.md          # Agent-specific workflows
│   └── tools/                   # 7 specialized tools
│       ├── resolve_channel_handles.py
│       ├── list_recent_uploads.py
│       ├── read_sheet_links.py
│       ├── extract_youtube_from_page.py
│       ├── save_video_metadata.py
│       ├── enqueue_transcription.py
│       └── remove_sheet_row.py
├── transcriber_agent/
│   ├── transcriber_agent.py     # AssemblyAI transcription processing
│   ├── instructions.md
│   └── tools/                   # 5 processing tools
│       ├── get_video_audio_url.py
│       ├── submit_assemblyai_job.py
│       ├── poll_transcription_job.py
│       ├── save_transcript_record.py
│       └── save_transcript_record.py
├── summarizer_agent/
│   ├── summarizer_agent.py      # GPT-4 content summarization
│   ├── instructions.md
│   └── tools/                   # 6 summary tools
│       ├── generate_short_summary.py
│       ├── process_summary_workflow.py
│       ├── save_summary_record.py
│       ├── save_summary_record_enhanced.py
│       ├── store_short_in_zep.py
│       └── save_summary_record.py
├── observability_agent/
│   ├── observability_agent.py   # Operations monitoring and alerting
│   ├── instructions.md
│   └── tools/                   # 11 monitoring tools
│       ├── alert_engine.py
│       ├── format_slack_blocks.py
│       ├── generate_daily_digest.py
│       ├── llm_observability_metrics.py
│       ├── monitor_dlq_trends.py
│       ├── monitor_quota_state.py
│       ├── monitor_transcription_budget.py
│       ├── report_daily_summary.py
│       ├── send_error_alert.py
│       ├── send_slack_message.py
│       └── stuck_job_scanner.py
├── linkedin_agent/
│   ├── linkedin_agent.py        # LinkedIn content ingestion
│   ├── instructions.md
│   └── tools/                   # 9 LinkedIn tools
│       ├── get_user_posts.py
│       ├── get_post_comments.py
│       ├── get_post_reactions.py
│       ├── get_user_comment_activity.py
│       ├── normalize_linkedin_content.py
│       ├── deduplicate_entities.py
│       ├── compute_linkedin_stats.py
│       ├── upsert_to_zep_group.py
│       └── save_ingestion_record.py
├── strategy_agent/
│   ├── strategy_agent.py        # Content analysis and strategy synthesis
│   ├── instructions.md
│   └── tools/                   # 10 strategy tools
│       ├── fetch_corpus_from_zep.py
│       ├── compute_engagement_signals.py
│       ├── extract_keywords_and_phrases.py
│       ├── cluster_topics_embeddings.py
│       ├── classify_post_types.py
│       ├── analyze_tone_of_voice.py
│       ├── mine_trigger_phrases.py
│       ├── generate_content_briefs.py
│       ├── synthesize_strategy_playbook.py
│       └── save_strategy_artifacts.py
├── drive_agent/
│   ├── drive_agent.py           # Google Drive knowledge management
│   ├── instructions.md
│   └── tools/                   # 7 Drive tools
│       ├── list_tracked_targets_from_config.py
│       ├── resolve_folder_tree.py
│       ├── list_drive_changes.py
│       ├── fetch_file_content.py
│       ├── extract_text_from_document.py
│       ├── upsert_drive_docs_to_zep.py
│       └── save_drive_ingestion_record.py
├── core/
│   ├── audit_logger.py          # TASK-AUDIT-0041: Centralized audit logging
│   ├── reliability.py          # Dead letter queue and retry logic
│   ├── sheets.py               # Google Sheets utilities
│   └── idempotency.py          # Core naming and deduplication
├── config/
│   ├── settings.yaml           # Runtime configuration
│   ├── loader.py              # Configuration management
│   └── env_loader.py          # Environment validation
├── services/
│   ├── firebase/
│   │   ├── functions/         # Firebase Functions v2 for scheduling
│   │   │   ├── main.py       # Entry points
│   │   │   ├── scheduler.py  # Scheduled and event-driven functions
│   │   │   └── requirements.txt  # Firebase dependencies
│   │   └── deployment.md     # Deployment guide
│   └── firestore/
│       └── indexes.md        # Firestore index configuration
├── tests/                     # Comprehensive test suite (72 test files)
│   ├── test_config.py        # Configuration tests
│   ├── test_env_loader.py    # Environment tests
│   ├── test_audit_logger.py  # Audit logging tests
│   ├── drive_tools/          # Drive Agent test suite (8 test files)
│   ├── linkedin_tools/       # LinkedIn Agent test suite
│   ├── observability_tools/  # Observability Agent test suite
│   ├── orchestrator_tools/   # Orchestrator Agent test suite
│   └── [55 additional test files across all agents]
├── planning/
│   ├── tasks.md              # Active task tracking
│   └── archive/              # Completed tasks and documentation
├── docs/                     # Comprehensive documentation
│   ├── claude.md            # Development guidance for Claude Code
│   ├── testing.md           # Testing guide
│   ├── environment.md       # Environment setup guide
│   ├── agents_overview.md   # Agent architecture overview
│   ├── quick_overview.md    # Project quick start
│   ├── contracts.md         # API contracts
│   ├── module_execution.md  # Module execution patterns
│   ├── firebase_implementation.md
│   ├── audit_logging_implementation.md
│   ├── idempotency_implementation.md
│   ├── reliability_implementation.md
│   └── sheets_implementation.md
├── firebase.json              # Firebase project configuration
├── firestore.rules           # Security rules (admin-only)
├── firestore.indexes.json    # Firestore composite indexes
├── changelog.md              # Project change history
├── requirements.txt          # Python dependencies
└── pyproject.toml           # Python project configuration
```

## 🚀 Quick Start

### Prerequisites

- Python 3.13+
- Virtual environment support
- Google Cloud Project with Firestore enabled
- API credentials for: OpenAI, AssemblyAI, YouTube, Slack, Zep

### Installation

1. **Clone and setup environment:**

   ```bash
   cd agents/autopiloot
   python3 -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure PYTHONPATH (REQUIRED):**

   ```bash
   # CRITICAL: Set PYTHONPATH to enable proper module imports
   export PYTHONPATH=.

   # For permanent setup, add to your shell profile:
   echo 'export PYTHONPATH=.' >> ~/.bashrc  # or ~/.zshrc
   ```

   **Why PYTHONPATH is required:**
   - All 151+ Python files have been cleaned to remove `sys.path` manipulation
   - Proper package structure relies on PYTHONPATH=. for imports
   - pytest.ini automatically sets this for test discovery
   - Without PYTHONPATH, imports from `config/`, `core/`, and agent modules will fail

3. **Configure credentials:**

   ```bash
   cp .env.template .env
   # Edit .env with your API keys (see docs/environment.md for details)

   # Validate configuration (requires PYTHONPATH=.)
   python config/env_loader.py
   ```

4. **Test the system:**

   ```bash
   # PYTHONPATH=. is automatically set by pytest.ini for tests
   # Run comprehensive test suite (140+ tests)
   python -m unittest discover tests -v

   # Test specific components
   python -m unittest tests.test_audit_logger -v

   # Test individual tools (requires PYTHONPATH=.)
   python scraper_agent/tools/save_video_metadata.py
   ```

5. **Run the agency:**
   ```bash
   # Ensure PYTHONPATH is set before running
   export PYTHONPATH=.
   python agency.py
   ```

## 📚 Documentation Index

- Project Overview
  - [readme.md](readme.md)
  - [docs/QUICK_OVERVIEW.md](docs/QUICK_OVERVIEW.md)
  - [docs/AGENTS_OVERVIEW.md](docs/AGENTS_OVERVIEW.md)
  - [docs/agency_manifesto.md](docs/agency_manifesto.md)
- Agent Instructions
  - [orchestrator_agent/instructions.md](orchestrator_agent/instructions.md)
  - [scraper_agent/instructions.md](scraper_agent/instructions.md)
  - [transcriber_agent/instructions.md](transcriber_agent/instructions.md)
  - [summarizer_agent/instructions.md](summarizer_agent/instructions.md)
  - [observability_agent/instructions.md](observability_agent/instructions.md)
- Implementation Guides
  - [docs/IDEMPOTENCY_IMPLEMENTATION.md](docs/IDEMPOTENCY_IMPLEMENTATION.md)
  - [docs/SHEETS_IMPLEMENTATION.md](docs/SHEETS_IMPLEMENTATION.md)
  - [docs/RELIABILITY_IMPLEMENTATION.md](docs/RELIABILITY_IMPLEMENTATION.md)
  - [docs/FIREBASE_IMPLEMENTATION.md](docs/FIREBASE_IMPLEMENTATION.md)
  - [docs/AUDIT_LOGGING_IMPLEMENTATION.md](docs/AUDIT_LOGGING_IMPLEMENTATION.md)
- Testing & Environment
  - [docs/testing.md](docs/testing.md)
  - [docs/environment.md](docs/environment.md)
- Firebase
  - [services/firebase/DEPLOYMENT.md](services/firebase/DEPLOYMENT.md)
  - [services/firebase/functions/readme.md](services/firebase/functions/readme.md)
- Firestore
  - [services/firestore/indexes.md](services/firestore/indexes.md)
- Development Guidance
  - [docs/claude.md](docs/claude.md)

## 🏗️ Technology Stack

### Core Framework

- **Agency Swarm v1.0.0** - Multi-agent orchestration
- **Python 3.13** - Primary language
- **Pydantic** - Data validation and type safety

### AI & APIs

- **OpenAI GPT-4.1** (temp: 0.2, ~1500 tokens) - Coaching summaries
- **AssemblyAI** - Professional transcription with speaker labels
- **YouTube Data API v3** - Video discovery and metadata
- **Google APIs** - Drive storage, Sheets processing
- **Slack API** - Rich notifications with Block Kit
- **Zep GraphRAG** - Semantic search and content discovery

### Infrastructure

- **Google Cloud Firestore** - Event broker and data persistence
- **Firebase Functions v2** - Scheduled execution (01:00 CET daily)
- **Cloud Scheduler** - Cron triggers with DST handling
- **Google Drive** - Transcript and summary storage

### Observability

- **Langfuse** (optional) - LLM tracing and observability
- **Custom audit logging** - TASK-AUDIT-0041 compliance
- **Structured logging** - Comprehensive error tracking

## 📊 Data Architecture

### Firestore Collections

```typescript
// Core data flow
videos/{video_id}              // Discovery and status tracking
├── url, title, published_at, channel_id, duration_sec
├── source: "scrape" | "sheet"
├── status: "discovered" → "transcription_queued" → "transcribed" → "summarized"
└── timestamps: created_at, updated_at

transcripts/{video_id}         // Transcription results and costs
├── transcript_drive_id_txt, transcript_drive_id_json
├── digest (SHA-256), created_at
└── costs: { transcription_usd }

summaries/{video_id}          // Multi-platform summary storage
├── short_drive_id, zep_doc_id, prompt_id, prompt_version
├── rag_refs[], transcript_doc_ref
├── token_usage: { input_tokens, output_tokens }
└── metadata: bullets_count, concepts_count, zep_integration

// Operational collections
jobs/transcription/{job_id}    // Job queue management
costs_daily/{YYYY-MM-DD}      // Budget tracking and alerting
audit_logs/{auto_id}          // Security compliance (TASK-AUDIT-0041)
alert_throttling/{alert_type} // 1-per-hour throttling policy
jobs_deadletter/{job_id}      // Failed operations with retry exhaustion
```

### Status Progression

```
discovered → transcription_queued → transcribed → summarized
     ↓              ↓                    ↓            ↓
  Firestore     Job Queue           Drive+Cost    Zep+Drive+Summary
```

## 🔧 Configuration

### Runtime Settings (`config/settings.yaml`)

```yaml
# Content discovery
sheet: "1AbC2defGhIJkLmNoPqRSTuVwxyz0123456789" # Google Sheet for backfill
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

budgets:
  transcription_daily_usd: 5.0

# Business rules
idempotency:
  max_video_duration_sec: 4200 # 70 minutes

# Reliability settings
reliability:
  max_retry_attempts: 3
  base_delay_seconds: 60 # Exponential backoff: 60s → 120s → 240s
```

## 🧪 Testing Framework

Comprehensive test suite with **140+ test files** achieving **85% overall coverage**:

### Test Coverage by Agent

**7 of 8 agents meet 80%+ threshold** ✅

| Agent | Coverage | Status | Tools | Tests | Report |
|-------|----------|--------|-------|-------|--------|
| Orchestrator | 99% | ✅ Excellent | 10/10 at 100% | 169 tests | `coverage/orchestrator_agent/` |
| Scraper | 90% | ✅ Excellent | 6 perfect | 117 tests | `coverage/scraper_agent/` |
| LinkedIn | 87% | ✅ Good | 3 perfect | 302 tests | `coverage/linkedin_agent/` |
| Strategy | 86% | ✅ Good | 4 perfect | 288 tests | `coverage/strategy_agent/` |
| Summarizer | 84% | ✅ Good | 7 perfect | 42 tests | `coverage/summarizer_agent/` |
| Drive | 82% | ✅ Good | 4 perfect | 343 tests | `coverage/drive_agent/` |
| Transcriber | 80% | ✅ Good | 3 perfect | 67 tests | `coverage/transcriber_agent/` |
| Observability | 79% | ⚠️ Needs work | 5 perfect | 543 tests | `coverage/observability_agent/` |

### Running Tests

```bash
# Run all tests with coverage
cd autopiloot
export PYTHONPATH=.
coverage erase
coverage run --source=. -m unittest discover tests -v
coverage report
coverage html  # Generate HTML report in htmlcov/

# Test individual agents (with proper isolation)
coverage erase
coverage run --source=orchestrator_agent -m unittest discover tests/orchestrator_tools -p "test_*.py" -v
coverage html --include="orchestrator_agent/*" -d coverage/orchestrator_agent

# Agent-specific test commands
coverage run --source=drive_agent -m unittest discover tests/drive_tools -p "test_*.py" -v
coverage run --source=linkedin_agent -m unittest discover tests/linkedin_tools -p "test_*.py" -v
coverage run --source=strategy_agent -m unittest discover tests/strategy_tools -p "test_*.py" -v
coverage run --source=summarizer_agent -m unittest discover tests/summarizer_tools -p "test_*.py" -v
coverage run --source=observability_agent -m unittest discover tests/observability_tools -p "test_*.py" -v
coverage run --source=scraper_agent -m unittest tests.test_extract_youtube_from_page_comprehensive tests.test_resolve_channel_handles_100_coverage tests.test_list_recent_uploads_100_coverage tests.test_save_video_metadata_100_coverage tests.test_read_sheet_links_working tests.test_remove_sheet_row_100_coverage tests.test_enqueue_transcription_100_coverage -v
coverage run --source=transcriber_agent -m unittest tests.test_get_video_audio_url_comprehensive tests.test_poll_transcription_job_fixed tests.test_save_transcript_record_100_coverage tests.test_save_transcript_record_comprehensive tests.test_submit_assemblyai_job_fixed -v

# View HTML reports
open coverage/orchestrator_agent/index.html
open coverage/drive_agent/index.html
open coverage/linkedin_agent/index.html

# Component-specific tests
python -m unittest tests.test_audit_logger -v     # Audit logging tests
python -m unittest tests.test_config -v           # Configuration tests
python -m unittest tests.test_reliability -v      # Error handling tests
python -m unittest tests.test_sheets -v           # Google Sheets tests

# Tool integration tests (86 total tools)
python drive_agent/tools/extract_text_from_document.py
python linkedin_agent/tools/compute_linkedin_stats.py
python strategy_agent/tools/synthesize_strategy_playbook.py
python observability_agent/tools/send_error_alert.py
```

### Test Coverage Highlights

- ✅ **Orchestrator Agent**: 99% coverage - ALL 10 tools at 100%
- ✅ **Drive Agent**: 82% coverage - 4 tools at 100%
- ✅ **LinkedIn Agent**: 87% coverage - Comprehensive RapidAPI mocking
- ✅ **Strategy Agent**: 86% coverage - NLP analysis and playbook synthesis
- ✅ **Summarizer Agent**: 84% coverage - GPT-4 integration testing
- ✅ **Scraper Agent**: 90% coverage - YouTube API integration
- ✅ **Transcriber Agent**: 80% coverage - AssemblyAI workflow testing
- ⚠️ **Observability Agent**: 79% coverage - Needs minor improvement

**Test Infrastructure:**
- Configuration loading and validation
- Environment variable management
- Error handling and retry logic
- Audit logging and compliance
- API integration with comprehensive mocking
- Business rule enforcement
- Multi-format content processing (PDF, DOCX, HTML, CSV)
- Test isolation to prevent interference (agent-specific directories)

## 🚀 Deployment

### Firebase Functions

```bash
# Deploy scheduled functions
cd firebase
firebase deploy --only functions

# Test locally
firebase emulators:start --only functions,firestore
```

### Production Checklist

- [ ] All environment variables configured
- [ ] Google service account credentials valid
- [ ] Firestore indexes deployed
- [ ] Firebase Functions deployed
- [ ] Slack workspace and bot token configured
- [ ] Test end-to-end workflow with sample video

## 🔒 Security & Compliance

### Security Features

- **No PII processing** - Only public YouTube content
- **Admin-only Firestore** - Server-side security rules
- **Environment-based secrets** - No hardcoded credentials
- **Minimal OAuth scopes** - Drive and Sheets access only
- **Audit logging** - TASK-AUDIT-0041 compliance with structured trails

### Budget Controls

- **Daily limits**: $5 transcription budget with 80% alerts
- **Duration limits**: 70-minute video maximum
- **Rate limiting**: Respectful API usage with exponential backoff
- **Dead letter queues**: 3-retry limit with failure isolation

## 📋 Implementation Status

### ✅ Completed (All 85 tasks)

- **Configuration System**: YAML + environment validation (Tasks 00-04)
- **8-Agent Architecture**: 86 production tools across 8 specialized agents with snake_case naming (Tasks 06-85)
- **Multi-Platform Content Processing**: YouTube, LinkedIn, Google Drive integration (Tasks 71-85)
- **Core Infrastructure**: Firebase Functions, Firestore, scheduling (Tasks 01, 61-62)
- **Reliability System**: Dead letter queues, retry logic, quota management (Tasks 04, 24-25)
- **Audit Logging**: TASK-AUDIT-0041 compliance (Task 41)
- **Comprehensive Testing**: 72 test files with complete agent coverage (Tasks 54, 59-60, 36)
- **Documentation**: Complete documentation suite with 36 ADR entries (Tasks 55-56)
- **Observability Framework**: Enterprise monitoring and alerting (Tasks 40, 51)
- **Strategic Analysis**: NLP-powered content analysis and playbook synthesis (Tasks 77-80)
- **Knowledge Management**: Zep GraphRAG integration across all content sources (Tasks 19, 75, 84)

### 🎯 Production Ready Features

- **Daily Automation**: 01:00 CET scheduling with DST handling
- **Cost Controls**: Real-time budget monitoring with Slack alerts
- **Error Recovery**: Exponential backoff with dead letter queue
- **Operational Monitoring**: Rich Slack notifications with throttling
- **Data Integrity**: Atomic transactions and idempotent operations
- **Security Compliance**: Comprehensive audit trail and PII avoidance

## 📚 Documentation

- **[docs/modular-architecture.md](docs/modular-architecture.md)** - Complete modular architecture guide
- **[docs/claude.md](docs/claude.md)** - Development guidance and common commands
- **[docs/testing.md](docs/testing.md)** - Comprehensive testing instructions
- **[docs/environment.md](docs/environment.md)** - Environment setup guide
- **[docs/AUDIT_LOGGING_IMPLEMENTATION.md](docs/AUDIT_LOGGING_IMPLEMENTATION.md)** - Security compliance details
- **[planning/prd.mdc](planning/prd.mdc)** - Product requirements document
- **[ADR System](.cursor/rules/ADR.mdc)** - Architectural decision records

## 🤝 Contributing

This project follows Agency Swarm v1.0.0 patterns with modular architecture:

### Quick Agent Development

Generate a new agent in seconds with the CLI scaffold:

```bash
# Generate complete agent structure
python scripts/new_agent.py \
  --name "Content Analyzer" \
  --description "AI-powered content analysis and insights" \
  --tools "analyze_sentiment" "extract_topics" "generate_insights" \
  --environment-vars "API_KEY" "MODEL_URL"

# Agent is automatically added to settings.yaml and ready to use
```

### Development Standards

1. **Tools**: Inherit from `agency_swarm.tools.BaseTool`
2. **Validation**: Use Pydantic Field validation
3. **Testing**: Include test blocks in all tools
4. **Documentation**: Update ADRs for architectural decisions
5. **Configuration**: Use settings.yaml + environment variables
6. **Modular Design**: Follow scaffold-generated patterns

## 🔧 Development Scripts

- `scripts/new_agent.py`: CLI scaffold to generate a new agent (folders, tools, instructions). Example:
  ```bash
  python scripts/new_agent.py --name "Content Analyzer" --description "AI-powered content analysis and insights"
  ```
- `scripts/check_tool_filenames_snake_case.sh`: Enforces snake_case tool filenames. Run locally or in CI:
  ```bash
  bash scripts/check_tool_filenames_snake_case.sh
  ```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Agency Swarm**: [Documentation](https://agency-swarm.ai) | [GitHub](https://github.com/VRSEN/agency-swarm)
- **Project Issues**: Create GitHub issues for bugs or feature requests
- **Development**: See docs/claude.md for common development patterns

---

**Status**: Production Ready ✅
**Latest Update**: 2025-09-19
**Agent Count**: 8 agents, 86 tools (all snake_case)
**Test Coverage**: 72 comprehensive test files
**Tasks Completed**: 85/85 (100%)
