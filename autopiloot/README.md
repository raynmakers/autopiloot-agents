# Autopiloot Agency

A production-ready AI agent swarm built with Agency Swarm v1.0.0 for automated YouTube content processing, transcription, and business-focused summarization.

## Overview

Autopiloot is a comprehensive multi-agent system that automates the discovery, transcription, and summarization of expert content from YouTube, specifically targeting business coaching and entrepreneurial content. The system processes videos from channels like @AlexHormozi and transforms them into actionable insights for content creators and entrepreneurs.

### Target Users

- Entrepreneurs creating content primarily for LinkedIn
- Business coaches and consultants with 6-figure+ revenue
- Content creators looking to streamline research and insight generation

### Value Proposition

End-to-end automation of content research, transcription, and summarization with:

- ✅ Daily video discovery and processing
- ✅ High-quality AI transcription with cost controls ($5/day budget)
- ✅ Coaching-focused summaries with actionable insights
- ✅ Semantic search and knowledge management via Zep GraphRAG
- ✅ Complete audit trail and operational monitoring

## Architecture Overview

**Event-Driven Broker Architecture**: Firestore serves as both data store and event broker, enabling real-time agent coordination and status tracking.

### 🤖 Agent Structure

#### ScraperAgent (CEO)

**Role**: Content discovery and metadata management

- YouTube channel handle resolution and uploads discovery
- Google Sheets backfill processing
- Video metadata storage with business rule validation (70-min limit)
- Transcription job queue management

#### TranscriberAgent

**Role**: Audio processing and transcript generation

- AssemblyAI integration with exponential backoff polling
- Dual-format storage (JSON + TXT) to Google Drive
- Cost tracking and budget monitoring integration
- Firestore transcript metadata management

#### SummarizerAgent

**Role**: Content analysis and insight generation

- GPT-4.1 powered coaching-focused summaries
- Zep GraphRAG storage for semantic search
- Multi-platform persistence (Firestore, Drive, Zep)
- Enhanced metadata and reference linking

#### ObservabilityAgent

**Role**: Operations monitoring and alerting

- Real-time budget monitoring with 80% threshold alerts
- Slack notifications with 1-per-type-per-hour throttling
- Error alerting and operational health monitoring
- Rich Slack Block Kit formatting for notifications

## Project Structure

```
autopiloot/
├── agency.py                     # Main agency orchestration
├── agency_manifesto.md           # Shared operational standards
├── scraper_agent/
│   ├── scraper_agent.py         # Agent definition and configuration
│   ├── instructions.md          # Agent-specific workflows
│   └── tools/                   # 7 specialized tools
│       ├── ResolveChannelHandles.py
│       ├── ListRecentUploads.py
│       ├── ReadSheetLinks.py
│       ├── ExtractYouTubeFromPage.py
│       ├── SaveVideoMetadata.py
│       ├── EnqueueTranscription.py
│       └── RemoveSheetRow.py
├── transcriber_agent/
│   ├── transcriber_agent.py     # Agent definition
│   ├── instructions.md
│   └── tools/                   # 5 processing tools
│       ├── get_video_audio_url.py
│       ├── submit_assemblyai_job.py
│       ├── poll_transcription_job.py
│       ├── store_transcript_to_drive.py
│       └── save_transcript_record.py
├── summarizer_agent/
│   ├── summarizer_agent.py      # Agent definition
│   ├── instructions.md
│   └── tools/                   # 8 summary tools
│       ├── GenerateShortSummary.py
│       ├── StoreShortInZep.py
│       ├── StoreShortSummaryToDrive.py
│       ├── SaveSummaryRecord.py
│       ├── SaveSummaryRecordEnhanced.py
│       ├── UpsertSummaryToZep.py
│       └── ProcessSummaryWorkflow.py
├── observability_agent/
│   ├── observability_agent.py   # Agent definition
│   ├── instructions.md
│   └── tools/                   # 4 monitoring tools
│       ├── format_slack_blocks.py
│       ├── send_slack_message.py
│       ├── monitor_transcription_budget.py
│       └── send_error_alert.py
├── core/
│   ├── audit_logger.py          # TASK-AUDIT-0041: Centralized audit logging
│   ├── reliability.py          # Dead letter queue and retry logic
│   ├── sheets.py               # Google Sheets utilities
│   └── idempotency.py          # Core naming and deduplication
├── config/
│   ├── settings.yaml           # Runtime configuration
│   ├── loader.py              # Configuration management
│   └── env_loader.py          # Environment validation
├── firebase/
│   ├── functions/             # Firebase Functions v2 for scheduling
│   │   ├── main.py           # Entry points
│   │   ├── scheduler.py      # Scheduled and event-driven functions
│   │   └── requirements.txt  # Firebase dependencies
│   ├── firebase.json         # Firebase project configuration
│   ├── firestore.rules      # Security rules (admin-only)
│   └── firestore.indexes.json
├── tests/                     # Comprehensive test suite
│   ├── test_config.py        # Configuration tests (11 tests)
│   ├── test_env_loader.py    # Environment tests (17 tests)
│   ├── test_audit_logger.py  # Audit logging tests (15 tests)
│   └── [25 additional test files]
├── planning/
│   ├── prd.mdc              # Product Requirements Document
│   └── tasks/               # Implementation tasks (22 completed)
├── CLAUDE.md                # Development guidance for Claude Code
├── TESTING.md              # Comprehensive testing guide
├── ENVIRONMENT.md          # Environment setup guide
├── AUDIT_LOGGING_IMPLEMENTATION.md
├── requirements.txt        # Python dependencies
└── env.template           # Environment variables template
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

2. **Configure credentials:**

   ```bash
   cp env.template .env
   # Edit .env with your API keys (see ENVIRONMENT.md for details)

   # Validate configuration
   python config/env_loader.py
   ```

3. **Test the system:**

   ```bash
   # Run comprehensive test suite (60+ tests)
   python -m unittest discover tests -v

   # Test specific components
   python -m unittest tests.test_audit_logger -v
   python scraper_agent/tools/SaveVideoMetadata.py
   ```

4. **Run the agency:**
   ```bash
   python agency.py
   ```

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

Comprehensive test suite with **60+ tests** across all components:

```bash
# Run all tests
python -m unittest discover tests -v

# Component-specific tests
python -m unittest tests.test_audit_logger -v     # Audit logging (15 tests)
python -m unittest tests.test_config -v           # Configuration (11 tests)
python -m unittest tests.test_reliability -v      # Error handling (22 tests)
python -m unittest tests.test_sheets -v           # Google Sheets (18 tests)

# Tool integration tests
python scraper_agent/tools/SaveVideoMetadata.py
python transcriber_agent/tools/poll_transcription_job.py
python summarizer_agent/tools/GenerateShortSummary.py
python observability_agent/tools/send_error_alert.py
```

**Test Coverage:**

- ✅ All 25 production tools with standalone test blocks
- ✅ Configuration loading and validation
- ✅ Environment variable management
- ✅ Error handling and retry logic
- ✅ Audit logging and compliance
- ✅ API integration patterns
- ✅ Business rule enforcement

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

### ✅ Completed (22/22 tasks)

- **Configuration System**: YAML + environment validation (28 tests)
- **Agent Architecture**: 4 agents with 25 production tools
- **Core Infrastructure**: Firebase Functions, Firestore, scheduling
- **Reliability System**: Dead letter queues, retry logic, quota management
- **Audit Logging**: TASK-AUDIT-0041 compliance with 15 tests
- **Comprehensive Testing**: 60+ tests across all components
- **Documentation**: ADR system, testing guides, deployment docs

### 🎯 Production Ready Features

- **Daily Automation**: 01:00 CET scheduling with DST handling
- **Cost Controls**: Real-time budget monitoring with Slack alerts
- **Error Recovery**: Exponential backoff with dead letter queue
- **Operational Monitoring**: Rich Slack notifications with throttling
- **Data Integrity**: Atomic transactions and idempotent operations
- **Security Compliance**: Comprehensive audit trail and PII avoidance

## 📚 Documentation

- **[CLAUDE.md](CLAUDE.md)** - Development guidance and common commands
- **[TESTING.md](TESTING.md)** - Comprehensive testing instructions
- **[ENVIRONMENT.md](ENVIRONMENT.md)** - Environment setup guide
- **[AUDIT_LOGGING_IMPLEMENTATION.md](AUDIT_LOGGING_IMPLEMENTATION.md)** - Security compliance details
- **[planning/prd.mdc](planning/prd.mdc)** - Product requirements document
- **[ADR System](.cursor/rules/ADR.mdc)** - Architectural decision records

## 🤝 Contributing

This project follows Agency Swarm v1.0.0 patterns:

1. **Tools**: Inherit from `agency_swarm.tools.BaseTool`
2. **Validation**: Use Pydantic Field validation
3. **Testing**: Include test blocks in all tools
4. **Documentation**: Update ADRs for architectural decisions
5. **Configuration**: Use settings.yaml + environment variables

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Agency Swarm**: [Documentation](https://agency-swarm.ai) | [GitHub](https://github.com/VRSEN/agency-swarm)
- **Project Issues**: Create GitHub issues for bugs or feature requests
- **Development**: See CLAUDE.md for common development patterns

---

**Status**: Production Ready ✅  
**Latest Update**: 2025-09-15  
**Agent Count**: 4 agents, 25 tools  
**Test Coverage**: 60+ comprehensive tests
