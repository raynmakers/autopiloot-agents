# Autopiloot Agency - Quick System Overview

## 🎯 What It Does

Autopiloot is an **automated YouTube content processing pipeline** that:

1. **Discovers** videos from channels like @AlexHormozi daily
2. **Transcribes** them using AssemblyAI (professional quality)
3. **Summarizes** them into actionable business insights using GPT-4.1
4. **Stores** everything in multiple formats for search and retrieval
5. **Monitors** costs and sends Slack alerts for operational issues

## 🏗️ System Architecture

```
OrchestratorAgent (CEO) → plans/dispatches/enforces policies
    ↓
ScraperAgent → discovers videos, saves metadata, enqueues jobs
    ↓
TranscriberAgent → extracts audio, creates transcripts
    ↓
SummarizerAgent → generates coaching-focused summaries
ObservabilityAgent → monitors budgets/health, sends alerts
```

**Data Flow**: Firestore acts as event broker, triggering the next agent when status changes.

## 🚀 How to Run the System

### Prerequisites Setup

```bash
# 1. Clone and setup
cd agents/autopiloot
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure environment
cp env.template .env
# Edit .env with your API keys (see below for required keys)

# 3. Validate setup
python config/env_loader.py
```

### Required API Keys (in `.env`)

```bash
# Core APIs
OPENAI_API_KEY=sk-your-openai-key
ASSEMBLYAI_API_KEY=your-assemblyai-key
YOUTUBE_DATA_API_KEY=your-youtube-key
SLACK_BOT_TOKEN=xoxb-your-slack-bot

# Google Cloud
GCP_PROJECT_ID=your-firebase-project
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GOOGLE_DRIVE_FOLDER_ID_TRANSCRIPTS=drive-folder-id
GOOGLE_DRIVE_FOLDER_ID_SUMMARIES=drive-folder-id

# Optional
ZEP_API_KEY=your-zep-key  # For semantic search
LANGFUSE_PUBLIC_KEY=your-langfuse-key  # For LLM observability
```

### Run the Agency

```bash
# Run the complete workflow
python agency.py

# This will:
# 1. Discover new videos from @AlexHormozi
# 2. Queue transcription jobs
# 3. Process transcripts when ready
# 4. Generate and store summaries
# 5. Send Slack notifications for budgets/errors
```

## 🧪 Manual Testing - Individual Components

### 1. **Configuration & Environment**

```bash
# Test configuration loading
python config/env_loader.py

# Test YAML settings
python -c "from config.loader import load_app_config; print(load_app_config())"
```

### 2. **ScraperAgent Tools** (Content Discovery)

```bash
# Test YouTube channel resolution
python scraper_agent/tools/ResolveChannelHandles.py

# Test video discovery
python scraper_agent/tools/ListRecentUploads.py

# Test Google Sheets reading
python scraper_agent/tools/ReadSheetLinks.py

# Test video metadata storage
python scraper_agent/tools/SaveVideoMetadata.py
```

### 3. **TranscriberAgent Tools** (Audio Processing)

```bash
# Test YouTube audio extraction
python transcriber_agent/tools/get_video_audio_url.py

# Test AssemblyAI job submission
python transcriber_agent/tools/submit_assemblyai_job.py

# Test transcription polling
python transcriber_agent/tools/poll_transcription_job.py

# Test Google Drive storage
python transcriber_agent/tools/store_transcript_to_drive.py
```

### 4. **SummarizerAgent Tools** (Content Analysis)

```bash
# Test GPT-4.1 summary generation
python summarizer_agent/tools/GenerateShortSummary.py

# Test Zep GraphRAG storage
python summarizer_agent/tools/StoreShortInZep.py

# Test complete summary workflow
python summarizer_agent/tools/ProcessSummaryWorkflow.py
```

### 5. **ObservabilityAgent Tools** (Monitoring)

```bash
# Test budget monitoring
python observability_agent/tools/monitor_transcription_budget.py

# Test Slack message formatting
python observability_agent/tools/format_slack_blocks.py

# Test error alerting
python observability_agent/tools/send_error_alert.py
```

### 6. **Core Systems**

```bash
# Test audit logging
python -c "from core.audit_logger import audit_logger; print(audit_logger.log_video_discovered('test123', 'scrape', 'TestAgent'))"

# Test reliability systems
python -c "from core.reliability import QuotaManager; qm = QuotaManager(); print(qm.check_youtube_quota())"
```

## 🧪 Comprehensive Testing

### Run All Tests

```bash
# Complete test suite (60+ tests)
python -m unittest discover tests -v

# Component-specific tests
python -m unittest tests.test_audit_logger -v      # Audit logging
python -m unittest tests.test_config -v            # Configuration
python -m unittest tests.test_reliability -v       # Error handling
python -m unittest tests.test_monitor_transcription_budget -v  # Budget monitoring
```

### Individual Test Categories

```bash
# Core system tests
python -m unittest tests.test_config tests.test_env_loader tests.test_audit_logger -v

# Agent workflow tests
python -m unittest tests.test_generate_short_summary tests.test_format_slack_blocks -v

# Integration tests
python -m unittest tests.test_store_transcript_to_drive tests.test_send_slack_message -v
```

## 📊 Production Deployment

### Firebase Functions (Automated Scheduling)

```bash
# Deploy for daily automation at 01:00 CET
cd firebase
firebase deploy --only functions

# This enables:
# - Daily video discovery and processing
# - Real-time budget monitoring
# - Automated Slack notifications
```

### Manual Workflow Testing

```bash
# Test complete workflow with a specific video
python -c "
from agency import AutopilootAgency
agency = AutopilootAgency()
result = agency.process_single_video('dQw4w9WgXcQ')  # Rick Roll for testing
print(result)
"
```

## 🔍 Monitoring & Debugging

### Check System Health

```bash
# View recent audit logs
python -c "
from google.cloud import firestore
db = firestore.Client()
logs = db.collection('audit_logs').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(10).get()
for log in logs: print(log.to_dict())
"

# Check daily costs
python -c "
from datetime import date
from google.cloud import firestore
db = firestore.Client()
today = date.today().isoformat()
cost_doc = db.document(f'costs_daily/{today}').get()
if cost_doc.exists: print(f'Today spent: ${cost_doc.to_dict().get(\"transcription_usd_total\", 0)}')
"
```

### View Slack Notifications

- Check `#ops-autopiloot` channel for:
  - ✅ Daily execution summaries
  - ⚠️ Budget threshold alerts (80% of $5/day)
  - 🚨 Error notifications with context
  - 📊 Operational health updates

## 💡 Quick Development Tips

### Add Your Own YouTube Channel

```bash
# Edit config/settings.yaml
scraper:
  handles: ["@AlexHormozi", "@YourChannel"]
  daily_limit_per_channel: 10
```

### Test With Single Video

```bash
# Process specific video ID manually
python scraper_agent/tools/SaveVideoMetadata.py
# Edit the test block with your video ID
```

### Debug Mode

```bash
# Enable verbose logging
export PYTHONPATH=.
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
# Run any component
"
```

## 🎯 Expected Results

After running successfully, you'll have:

- **Videos** discovered and stored in Firestore (`videos/` collection)
- **Transcripts** saved to Google Drive in TXT + JSON formats
- **Summaries** stored in Firestore, Drive, and Zep GraphRAG
- **Audit logs** tracking all operations (`audit_logs/` collection)
- **Cost tracking** with daily budget monitoring
- **Slack alerts** for operational status and issues

**Total processing time**: ~5-15 minutes per video (depending on length and AssemblyAI queue)  
**Daily budget**: $5 for transcription costs with 80% threshold alerts  
**Automation**: Runs daily at 01:00 Europe/Amsterdam via Firebase Functions

The system is designed to be **production-ready** with comprehensive error handling, audit trails, and operational monitoring. Each component can be tested individually before running the complete workflow.
