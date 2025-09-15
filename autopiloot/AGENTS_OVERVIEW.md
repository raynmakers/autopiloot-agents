# Autopiloot Agents Overview

This document provides detailed information about each agent in the Autopiloot Agency system.

## Agent Architecture

The Autopiloot Agency consists of 4 specialized agents following the Agency Swarm v1.0.0 framework:

- **ScraperAgent** (CEO) - Content discovery and orchestration
- **TranscriberAgent** - Audio processing and transcription
- **SummarizerAgent** - Content analysis and summarization
- **ObservabilityAgent** - Operations monitoring and alerting

## Communication Flow

```
ScraperAgent (CEO)
    ↓ ↑
    ├── TranscriberAgent
    │   ↓ ↑
    │   └── SummarizerAgent
    ↓ ↑
ObservabilityAgent (monitoring all)
```

---

## 🔍 ScraperAgent (CEO)

**Role**: Content discovery and metadata management  
**Status**: CEO (can communicate with all agents)  
**Tools**: 7 specialized discovery and management tools

### Primary Functions

- **YouTube Discovery**: Channel handle resolution and uploads discovery
- **Google Sheets Processing**: Backfill link extraction and management
- **Video Validation**: Duration limits, metadata extraction, business rule enforcement
- **Workflow Orchestration**: Transcription job queue management and agent coordination

### Tools Overview

| Tool                        | Purpose                                             | Integration                  |
| --------------------------- | --------------------------------------------------- | ---------------------------- |
| `ResolveChannelHandles.py`  | Convert @handles to YouTube channel IDs             | YouTube Data API             |
| `ListRecentUploads.py`      | Discover recent videos with checkpoint system       | YouTube Data API + Firestore |
| `ReadSheetLinks.py`         | Extract YouTube URLs from Google Sheets             | Google Sheets API            |
| `ExtractYouTubeFromPage.py` | Parse YouTube links from web pages                  | BeautifulSoup + HTTP         |
| `SaveVideoMetadata.py`      | Store video data with business rule validation      | Firestore + Audit Logging    |
| `EnqueueTranscription.py`   | Create transcription jobs with duplicate prevention | Firestore Transactions       |
| `RemoveSheetRow.py`         | Archive processed rows from Google Sheets           | Google Sheets API            |

### Key Features

- **Checkpoint System**: `lastPublishedAt` persistence for incremental processing
- **Business Rules**: 70-minute duration limit, daily channel limits (10 videos)
- **Idempotency**: Video ID-based deduplication preventing duplicates
- **Audit Trail**: All discovery actions logged per TASK-AUDIT-0041

### Configuration

```yaml
# settings.yaml
scraper:
  handles: ["@AlexHormozi"]
  daily_limit_per_channel: 10
```

---

## 🎵 TranscriberAgent

**Role**: Audio processing and transcript generation  
**Communication**: ScraperAgent → TranscriberAgent → SummarizerAgent  
**Tools**: 5 comprehensive transcription processing tools

### Primary Functions

- **Audio Extraction**: YouTube video to audio URL resolution
- **AssemblyAI Integration**: Professional transcription with speaker labels
- **Storage Management**: Dual-format storage (JSON + TXT) to Google Drive
- **Cost Tracking**: Budget monitoring with real-time cost calculations

### Tools Overview

| Tool                           | Purpose                                         | Integration                  |
| ------------------------------ | ----------------------------------------------- | ---------------------------- |
| `get_video_audio_url.py`       | Extract audio URLs from YouTube videos          | yt-dlp + YouTube API         |
| `submit_assemblyai_job.py`     | Submit transcription jobs to AssemblyAI         | AssemblyAI SDK               |
| `poll_transcription_job.py`    | Monitor job completion with exponential backoff | AssemblyAI SDK + Retry Logic |
| `store_transcript_to_drive.py` | Save transcripts in dual formats with metadata  | Google Drive API             |
| `save_transcript_record.py`    | Store metadata and update video status          | Firestore + Audit Logging    |

### Key Features

- **Exponential Backoff**: Configurable polling (60s → 120s → 240s)
- **Dual Format Storage**: JSON (machine processing) + TXT (human review)
- **Cost Integration**: Real-time budget tracking with $5/day limit
- **Quality Assurance**: SHA-256 integrity checking and metadata validation

### Reliability

- **Timeout Management**: Configurable job timeout (5min-2h)
- **Retry Logic**: Max attempts with dead letter queue integration
- **Error Isolation**: Graceful failure handling without workflow disruption

---

## 📝 SummarizerAgent

**Role**: Content analysis and insight generation  
**Communication**: TranscriberAgent → SummarizerAgent  
**Tools**: 8 advanced summarization and storage tools

### Primary Functions

- **LLM Summarization**: GPT-4.1 powered coaching-focused summaries
- **Multi-Platform Storage**: Zep GraphRAG, Google Drive, Firestore persistence
- **Semantic Search**: Zep integration for content discovery and retrieval
- **Enhanced Workflows**: Complete reference linking and metadata preservation

### Tools Overview

| Tool                           | Purpose                                     | Integration                   |
| ------------------------------ | ------------------------------------------- | ----------------------------- |
| `GenerateShortSummary.py`      | Create actionable business summaries        | OpenAI GPT-4.1 + Langfuse     |
| `StoreShortInZep.py`           | Save to Zep GraphRAG for semantic search    | Zep API                       |
| `StoreShortSummaryToDrive.py`  | Dual-format Drive storage (JSON + Markdown) | Google Drive API              |
| `SaveSummaryRecord.py`         | Basic Firestore summary records             | Firestore                     |
| `SaveSummaryRecordEnhanced.py` | Enhanced records with Zep references        | Firestore + Enhanced Metadata |
| `UpsertSummaryToZep.py`        | Advanced Zep integration with RAG refs      | Zep API + Enhanced Metadata   |
| `ProcessSummaryWorkflow.py`    | End-to-end orchestration tool               | Multi-platform Coordination   |

### Key Features

- **Adaptive Chunking**: Model-specific context optimization (GPT-4: 8k, GPT-4.1: 128k)
- **Coaching Focus**: Prompts optimized for actionable business insights
- **Observability**: Langfuse tracing with token usage and prompt versioning
- **Reference Integrity**: Complete linking between transcripts, summaries, and RAG docs

### Configuration

```yaml
# settings.yaml
llm:
  tasks:
    summarizer_generate_short:
      model: "gpt-4.1"
      temperature: 0.2
      max_output_tokens: 1500
      prompt_version: "v1"
```

---

## 🚨 ObservabilityAgent

**Role**: Operations monitoring and alerting  
**Communication**: Monitors all agents, sends alerts  
**Tools**: 4 comprehensive monitoring and notification tools

### Primary Functions

- **Budget Monitoring**: Real-time transcription cost tracking with 80% alerts
- **Error Alerting**: Structured Slack notifications with throttling policy
- **Operational Health**: System monitoring and failure detection
- **Rich Notifications**: Slack Block Kit formatting for improved readability

### Tools Overview

| Tool                              | Purpose                                                 | Integration         |
| --------------------------------- | ------------------------------------------------------- | ------------------- |
| `format_slack_blocks.py`          | Create rich Slack Block Kit notifications               | Slack Block Kit API |
| `send_slack_message.py`           | Send formatted messages to configured channels          | Slack API           |
| `monitor_transcription_budget.py` | Track daily spending with threshold alerts              | Firestore + Slack   |
| `send_error_alert.py`             | Error notifications with 1-per-type-per-hour throttling | Firestore + Slack   |

### Key Features

- **Smart Throttling**: 1 alert per type per hour prevents notification spam
- **Budget Precision**: Real-time cost calculation with 80% threshold alerting
- **Rich Formatting**: Alert-specific emojis, colors, and structured field presentation
- **Audit Integration**: All alerts logged to audit_logs collection

### Monitoring Capabilities

- **Daily Budget**: $5 transcription limit with percentage tracking
- **Error Categories**: API failures, quota exhaustion, workflow errors
- **Alert Types**: Budget warnings, error notifications, execution summaries
- **Channels**: Configurable Slack channels (default: #ops-autopiloot)

---

## Tool Development Standards

All agent tools follow consistent patterns:

### Agency Swarm Compliance

- **Inheritance**: `agency_swarm.tools.BaseTool`
- **Validation**: Pydantic Field validation for all parameters
- **Return Format**: JSON strings (not Dict objects)
- **Testing**: Comprehensive test blocks with `if __name__ == "__main__"`

### Error Handling

- **Graceful Degradation**: Tools continue operation despite failures
- **Structured Responses**: Consistent JSON error format across all tools
- **Audit Logging**: TASK-AUDIT-0041 compliance with structured metadata
- **Timeout Management**: Configurable timeouts for external API calls

### Integration Patterns

- **Environment Variables**: All secrets via environment configuration
- **Configuration Loading**: Centralized settings.yaml + env_loader patterns
- **Firestore Transactions**: Atomic operations for data consistency
- **Service Authentication**: Google service accounts for API access

---

## Agent Communication Protocol

### Message Flow

1. **ScraperAgent** discovers videos and creates transcription jobs
2. **TranscriberAgent** processes audio and stores transcripts
3. **SummarizerAgent** generates summaries with multi-platform storage
4. **ObservabilityAgent** monitors costs and sends alerts throughout

### Status Progression

```
discovered → transcription_queued → transcribed → summarized
     ↓              ↓                    ↓            ↓
  ScraperAgent  TranscriberAgent  SummarizerAgent  Complete
```

### Event Triggers

- **Firestore Writes**: Status updates trigger next agent in pipeline
- **Cost Events**: Transcript creation triggers budget monitoring
- **Error Events**: Failures trigger ObservabilityAgent error alerting
- **Audit Events**: All key actions logged for compliance and monitoring

---

## Development Guidelines

### Adding New Tools

1. **Inherit from BaseTool**: Use Agency Swarm v1.0.0 patterns
2. **Add Validation**: Implement Pydantic Field validation
3. **Include Testing**: Add comprehensive test block
4. **Update Instructions**: Document tool usage in agent instructions.md
5. **Audit Integration**: Add appropriate audit logging calls

### Testing Tools

```bash
# Run agent-specific tool tests
python scraper_agent/tools/SaveVideoMetadata.py
python transcriber_agent/tools/poll_transcription_job.py
python summarizer_agent/tools/GenerateShortSummary.py
python observability_agent/tools/send_error_alert.py
```

### Configuration Updates

- **settings.yaml**: Runtime configuration changes
- **env.template**: New environment variables
- **instructions.md**: Agent workflow updates
- **ADR updates**: Document architectural decisions

---

**Agents Status**: Production Ready ✅  
**Total Tools**: 25 across 4 agents  
**Framework**: Agency Swarm v1.0.0  
**Test Coverage**: Comprehensive with standalone tool tests
