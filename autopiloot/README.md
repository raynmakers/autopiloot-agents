# Autopiloot Agency

An AI agent swarm built with Agency Swarm v1.0 for automating content discovery, transcription, and summarization from YouTube content.

## Overview

Autopiloot is a multi-agent system designed to scrape and transform expert content into practical guidelines for writing new content and sales messaging. The system automates discovery, high-quality transcription, and actionable short summaries.

### Target Users

- Entrepreneurs creating content primarily for LinkedIn
- Users with at least 6-figure revenue looking to streamline content creation

### Value Proposition

Cut the waste in content creation, transcription, summarization, and follow-up analysis through end-to-end automation with searchable knowledge and internal alerting.

## Architecture

The system consists of 4 specialized agents:

### Agent A - Scraper Agent

**Role**: Discover new videos from `@AlexHormozi` and ingest human-provided links from Google Sheets

- Resolves YouTube channel handles to IDs
- Lists recent uploads within time windows
- Reads Google Sheet links and extracts YouTube URLs
- Saves video metadata to Firestore
- Enqueues transcription jobs

### Agent B - Transcriber Agent

**Role**: Transcribe videos using AssemblyAI with 70-minute duration limit

- Resolves video audio URLs
- Submits transcription jobs to AssemblyAI
- Polls for completion with webhook support
- Stores transcripts to Google Drive and Firestore

### Agent C - Summarizer Agent

**Role**: Generate actionable short summaries for coaching contexts

- Creates concise bullet summaries using GPT-4.1
- Stores summaries in Zep (GraphRAG) for retrieval
- Maintains explicit links to full transcripts
- Saves summary records to Firestore and Drive

### Agent D - Assistant Agent

**Role**: Monitor budgets and send internal alerts

- Tracks daily transcription costs (budget: $5/day)
- Sends Slack alerts at 80% budget threshold
- Formats and sends error notifications
- Monitors operational failures

## Project Structure

```
autopiloot/
├── config/
│   ├── settings.yaml          # Runtime configuration
│   ├── loader.py              # Configuration loader with validation
│   └── env_loader.py          # Environment variable loader and validation
├── planning/
│   ├── prd.mdc                # Product Requirements Document
│   └── tasks/                 # Implementation tasks (22 tasks)
│       ├── 00-config-yaml.mdc
│       ├── 00-env-config.mdc
│       ├── 01-scheduling-firebase.mdc
│       └── ...
├── firebase/
│   ├── functions/             # Firebase Functions v2
│   │   ├── main.py           # Scheduled and event-driven functions
│   │   ├── requirements.txt  # Python dependencies for Functions
│   │   └── README.md         # Firebase Functions documentation
│   ├── firebase.json         # Firebase project configuration
│   ├── firestore.rules       # Firestore security rules
│   └── firestore.indexes.json # Firestore indexes
├── core/
│   └── idempotency.py        # Core idempotency and naming logic
├── tests/
│   ├── __init__.py
│   ├── test_config.py        # Configuration loader tests (11 tests)
│   └── test_env_loader.py    # Environment loader tests (17 tests)
├── env.template              # Environment variables template
├── ENVIRONMENT.md            # Environment setup documentation
├── requirements.txt          # Python dependencies
└── venv/                     # Virtual environment
```

## Setup

### Prerequisites

- Python 3.13+
- Virtual environment support

### Installation

1. **Create and activate virtual environment:**

   ```bash
   cd agents/autopiloot
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**

   ```bash
   # Copy environment template and fill in your values
   cp env.template .env
   # Edit .env with your API keys and credentials
   ```

   See `ENVIRONMENT.md` for detailed setup instructions.

4. **Configure settings:**
   - Review `config/settings.yaml` for runtime configuration
   - Update any specific settings for your deployment

## Configuration

### Runtime Settings (`config/settings.yaml`)

```yaml
# Google Sheet ID for backfill links
sheet: "1AbC2defGhIJkLmNoPqRSTuVwxyz0123456789"

scraper:
  handles:
    - "@AlexHormozi"
  daily_limit_per_channel: 10

llm:
  default:
    model: "gpt-4.1"
    temperature: 0.2
  tasks:
    summarizer_generate_short:
      model: "gpt-4.1"
      temperature: 0.2
      prompt_id: "coach_v1"

notifications:
  slack:
    channel: "ops-autopiloot"

budgets:
  transcription_daily_usd: 5.0
```

### Environment Variables

Environment variables are managed through a comprehensive system with validation and error handling. See `ENVIRONMENT.md` for complete setup instructions.

**Quick setup:**

```bash
# Copy template and fill in your values
cp env.template .env

# Validate configuration
python config/env_loader.py
```

**Required variables:** OpenAI, AssemblyAI, YouTube, Slack API keys, Google credentials, Zep API key, and Google Drive folder IDs.

**Optional variables:** Langfuse observability, custom timezone, Slack signing secret.

## Technology Stack

### Core Framework

- **Agency Swarm v1.0** - Multi-agent orchestration framework
- **Python 3.13** - Primary programming language

### APIs & Services

- **YouTube Data API v3** - Video discovery and metadata
- **AssemblyAI** - Audio transcription service
- **OpenAI GPT-4.1** - Summary generation
- **Google Drive API** - File storage
- **Google Sheets API** - Backfill link management
- **Slack API** - Internal notifications
- **Zep** - GraphRAG for summary storage
- **Langfuse** - LLM observability (optional)

### Data Storage

- **Firestore** - Primary data store and event broker
- **Google Drive** - File artifacts storage

### Infrastructure

- **Firebase Functions v2** - Scheduled and event-driven automation
- **Cloud Scheduler** - Automated daily scraping triggers
- **Firebase Admin SDK** - Server-side data operations

### Collections Schema (Firestore)

```
videos/{video_id}:
  - url, title, published_at, channel_id, duration_sec
  - source, status, created_at, updated_at

transcripts/{video_id}:
  - transcript_drive_ids (txt, json)
  - digest, created_at, costs.transcription_usd

summaries/{video_id}:
  - short (zep_doc_id, drive_id, prompt_id, token_usage)
  - linkage (transcript references)
  - rag_refs, created_at

jobs/transcription/*:
  - video_id, submitted_at, status, retries

costs_daily/{YYYY-MM-DD}:
  - transcription_usd_total, alerts_sent

audit_logs/{auto_id}:
  - actor, action, entity, entity_id, timestamp, details
```

## Operational Features

### Scheduling

- **Daily scraping**: 01:00 Europe/Amsterdam (CET/CEST)
- **Budget monitoring**: Event-driven after transcription writes
- **DST handling**: Automatic via Cloud Scheduler

### Reliability Features

- **Idempotency**: Deduplication by YouTube video ID
- **Rate limiting**: Respectful API usage with exponential backoff
- **Error handling**: 3 retries with dead-letter queue
- **Cost controls**: Daily budget alerts at 80% threshold

### Security

- **No PII**: System handles only public content
- **Secrets management**: Environment variables only
- **Audit logging**: Key actions tracked in Firestore
- **Minimal OAuth scopes**: Drive and Sheets access only

## Development Status

### Completed Tasks ✅

- **00-config-yaml** - Configuration system with YAML settings and validation (11 tests)
- **00-env-config** - Environment variable system with comprehensive validation (17 tests)
- **Planning structure** - PRD and task organization moved to planning/ folder
- **Test framework** - Comprehensive test infrastructure with 28 total tests
- **Firebase infrastructure** - Functions, Firestore rules, and deployment configuration
- **Core utilities** - Idempotency and naming conventions

### Remaining Tasks (18 tasks)

- Firebase scheduling setup (task 01)
- Google Sheets workflow (task 03)
- Reliability and quotas (task 04)
- Agent tools development (tasks 05, 10-15, 20-22, 30-32, 40-41)
- Integration and observability features (tasks 37, 41)

## Testing

The project includes comprehensive unit tests for all implemented components. See `TESTING.md` for detailed testing instructions.

**Quick test run:**

```bash
# Run all tests (28 total: 11 config + 17 environment)
python -m unittest discover tests -v

# Run specific test modules
python -m unittest tests.test_config -v      # Configuration tests
python -m unittest tests.test_env_loader -v  # Environment tests

# Validate environment setup
python config/env_loader.py
```

## Maturity Level

**Status**: MVP (non-production)

- Keep infrastructure minimal
- Configure required environment variables before running
- Internal operations only (no end-user interfaces)

## Contributing

This project follows the Agency Swarm framework patterns. When adding new functionality:

1. Create tasks following the template in `agents/.cursor/rules/rules.mdc`
2. Implement tools using `BaseTool` or `@function_tool` decorator
3. Add comprehensive unit tests to the `tests/` directory
4. Update configuration as needed

## License

[Add your license information here]

## Support

For questions or issues, please refer to:

- [Agency Swarm Documentation](https://agency-swarm.ai)
- [Agency Swarm GitHub](https://github.com/VRSEN/agency-swarm)
- Project PRD: `planning/prd.mdc`
