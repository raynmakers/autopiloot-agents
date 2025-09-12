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
│   └── loader.py              # Configuration loader with validation
├── planning/
│   ├── prd.mdc                # Product Requirements Document
│   └── tasks/                 # Implementation tasks (22 tasks)
│       ├── 00-config-yaml.mdc
│       ├── 01-scheduling-firebase.mdc
│       └── ...
├── tests/
│   ├── __init__.py
│   └── test_config.py         # Configuration loader tests
├── requirements.txt           # Python dependencies
└── venv/                      # Virtual environment
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

3. **Configure settings:**
   - Review `config/settings.yaml` for runtime configuration
   - Set up environment variables (see Environment Variables section)

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

Create a `.env` file with the following variables:

```bash
# Required API Keys
OPENAI_API_KEY=your_openai_api_key
ASSEMBLYAI_API_KEY=your_assemblyai_api_key
SLACK_BOT_TOKEN=your_slack_bot_token

# Google Services
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
GOOGLE_DRIVE_FOLDER_ID_TRANSCRIPTS=your_drive_folder_id
GOOGLE_DRIVE_FOLDER_ID_SUMMARIES=your_drive_folder_id

# Zep GraphRAG
ZEP_API_KEY=your_zep_api_key
ZEP_COLLECTION=autopiloot_guidelines

# Observability (Optional)
LANGFUSE_PUBLIC_KEY=your_langfuse_public_key
LANGFUSE_SECRET_KEY=your_langfuse_secret_key
LANGFUSE_HOST=your_langfuse_host

# General
TIMEZONE=Europe/Amsterdam
```

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

### Data Storage

- **Firestore** - Primary data store and event broker
- **Google Drive** - File artifacts storage

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

- **00-config-yaml** - Configuration system with YAML settings and validation
- **Planning structure** - PRD and task organization
- **Test framework** - Unit test infrastructure with 11 comprehensive tests

### Remaining Tasks (20 tasks)

- Environment configuration
- Firebase scheduling setup
- Scraper agent tools (6 tools)
- Transcriber agent tools (4 tools)
- Summarizer agent tools (4 tools)
- Assistant agent tools (4 tools)
- Integration and observability features

## Testing

The project includes comprehensive unit tests for all implemented components. See `TESTING.md` for detailed testing instructions.

**Quick test run:**

```bash
# Run all tests
python -m unittest discover tests -v

# Run specific test module
python -m unittest tests.test_config -v
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
