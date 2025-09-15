# Firebase Functions for Autopiloot Agency

This directory contains Firebase Functions v2 for the Autopiloot project, implementing scheduled execution and event-driven budget monitoring for the multi-agent system.

## Overview

Firebase Functions provide cloud-native scheduling and automation for the Autopiloot Agency:

- **Scheduled Functions**: Daily agent execution at 01:00 Europe/Amsterdam
- **Event-Driven Functions**: Real-time budget monitoring triggered by transcript creation
- **Auto-scaling**: Serverless execution with automatic concurrency management
- **Integrated Logging**: Structured logging with audit trail integration

## Function Architecture

### 1. `daily_scraper_execution`

**Type**: Scheduled Function  
**Schedule**: `0 1 * * *` (Daily at 01:00 CET/CEST)  
**Timezone**: Europe/Amsterdam (automatic DST handling)  
**Purpose**: Execute the complete Autopiloot Agency workflow

```python
@scheduler_fn.on_schedule(
    schedule="0 1 * * *",
    timezone="Europe/Amsterdam",
    memory=512,
    timeout_sec=540  # 9 minutes
)
def daily_scraper_execution(event: ScheduledEvent) -> None:
    """Execute daily scraper workflow via Autopiloot Agency."""
```

**Workflow Steps:**

1. Initialize AutopilootAgency with production configuration
2. Execute ScraperAgent (CEO) discovery workflow
3. Trigger TranscriberAgent processing pipeline
4. Coordinate SummarizerAgent content analysis
5. Monitor via ObservabilityAgent with Slack notifications
6. Log execution results to audit_logs collection

### 2. `monitor_transcription_budget`

**Type**: Event-Driven Function  
**Trigger**: Firestore writes to `transcripts/{video_id}`  
**Purpose**: Real-time budget monitoring with 80% threshold alerting

```python
@firestore_fn.on_document_written(
    document="transcripts/{video_id}",
    memory=256,
    timeout_sec=180
)
def monitor_transcription_budget(event: firestore_fn.Event[firestore_fn.DocumentSnapshot | None]) -> None:
    """Monitor daily transcription budget and send threshold alerts."""
```

**Monitoring Logic:**

1. Extract transcription cost from new transcript document
2. Update daily cost aggregation in `costs_daily/{YYYY-MM-DD}`
3. Calculate budget percentage against configured limit ($5 default)
4. Send Slack alerts at 80% threshold via ObservabilityAgent tools
5. Log budget events to audit_logs for compliance

## Project Structure

```
firebase/functions/
├── main.py              # Entry points for all functions
├── scheduler.py         # Scheduled and event-driven function implementations
├── core.py             # Shared utilities and error handling
├── requirements.txt    # Python dependencies for Firebase runtime
└── readme.md          # This documentation
```

## Configuration

### Environment Variables

Firebase Functions inherit environment from the parent Autopiloot project:

**Required Environment Variables:**

```bash
# Core API Keys
OPENAI_API_KEY=sk-your-openai-key
ASSEMBLYAI_API_KEY=your-assemblyai-key
YOUTUBE_DATA_API_KEY=your-youtube-key
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token

# Google Cloud Configuration
GCP_PROJECT_ID=your-firebase-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Google Drive Folder IDs
GOOGLE_DRIVE_FOLDER_ID_TRANSCRIPTS=your-transcripts-folder
GOOGLE_DRIVE_FOLDER_ID_SUMMARIES=your-summaries-folder

# Zep Configuration (Optional)
ZEP_API_KEY=your-zep-api-key
ZEP_BASE_URL=https://api.getzep.com
ZEP_COLLECTION=autopiloot_guidelines
```

**Configuration Loading:**
Functions use the centralized environment loader from the main project:

```python
# Functions import core configuration
from core.env_loader import get_required_var, get_api_key
from config.loader import load_app_config

# Runtime configuration from settings.yaml
config = load_app_config()
daily_budget = config.get("budgets", {}).get("transcription_daily_usd", 5.0)
```

### Firebase Project Setup

```bash
# Initialize Firebase project
firebase init functions

# Configure project
firebase use your-project-id

# Enable required services
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
gcloud services enable firestore.googleapis.com
```

## Deployment

### Prerequisites

```bash
# Install Firebase CLI
npm install -g firebase-tools@latest

# Authenticate and select project
firebase login
firebase use your-project-id

# Verify Python 3.11+ availability
python3 --version  # Required for Firebase Functions v2
```

### Deploy Functions

```bash
# Navigate to project root (contains firebase.json)
cd /path/to/autopiloot

# Deploy all Firebase components
firebase deploy

# Deploy functions only
firebase deploy --only functions

# Deploy specific function
firebase deploy --only functions:daily_scraper_execution
firebase deploy --only functions:monitor_transcription_budget
```

### Deploy Firestore Configuration

```bash
# Deploy security rules (admin-only access)
firebase deploy --only firestore:rules

# Deploy indexes for efficient querying
firebase deploy --only firestore:indexes

# Deploy complete infrastructure
firebase deploy --only firestore,functions
```

## Local Development & Testing

### Emulator Setup

```bash
# Start complete emulator suite
firebase emulators:start --only functions,firestore

# Access emulator UI
open http://localhost:4000

# Functions endpoint
curl http://localhost:5001/your-project-id/europe-west1/daily_scraper_execution
```

### Testing Functions

```bash
# Test scheduled function manually
curl -X POST "http://localhost:5001/your-project-id/europe-west1/daily_scraper_execution" \
  -H "Content-Type: application/json" \
  -d '{}'

# Test event-driven function by creating transcript document
# Use Firestore emulator UI or admin SDK to write to transcripts/{video_id}
```

### Integration Testing

```bash
# Run agency tests locally
cd ../../  # Navigate to autopiloot root
python -m unittest tests.test_functions -v

# Test Firebase Functions integration
python firebase/functions/test_functions.py
```

## Monitoring & Observability

### Cloud Logging

```bash
# View all function logs
firebase functions:log

# Function-specific logs
firebase functions:log --only daily_scraper_execution
firebase functions:log --only monitor_transcription_budget

# Real-time log streaming
firebase functions:log --only daily_scraper_execution --follow
```

### Google Cloud Console

Monitor function execution in [Google Cloud Console](https://console.cloud.google.com/functions):

- **Metrics**: Invocations, execution time, memory usage, errors
- **Logs**: Structured logging with severity levels
- **Alerting**: Custom policies for function failures and budget thresholds

### Audit Trail

Functions automatically log execution events to Firestore:

```typescript
audit_logs/{auto_id}:
├── actor: "FirebaseFunction"
├── action: "daily_execution" | "budget_alert"
├── entity: "agency_workflow" | "transcription_budget"
├── entity_id: date | video_id
├── timestamp: UTC ISO 8601
└── details: { execution_time, result, alerts_sent }
```

### Slack Notifications

Functions send operational alerts to `#ops-autopiloot`:

- ✅ **Daily Execution Success**: Workflow completion summary
- ⚠️ **Budget Threshold**: 80% transcription budget reached
- 🚨 **Function Errors**: Execution failures with context
- 📊 **Weekly Summaries**: Usage and performance metrics

## Error Handling & Reliability

### Retry Policy

```python
# Scheduled functions: Automatic retry on failure
@scheduler_fn.on_schedule(
    schedule="0 1 * * *",
    timezone="Europe/Amsterdam",
    retry_config=scheduler_fn.RetryConfig(
        retry_count=3,
        max_backoff_duration=300
    )
)

# Event-driven functions: Dead letter queue for failures
@firestore_fn.on_document_written(
    document="transcripts/{video_id}",
    retry_config=firestore_fn.RetryConfig(
        retry_count=3,
        max_backoff_duration=180
    )
)
```

### Dead Letter Queue

Failed function executions are logged to `jobs_deadletter` collection:

```typescript
jobs_deadletter/{job_id}:
├── job_type: "firebase_function"
├── function_name: "daily_scraper_execution"
├── error_details: { message, stack_trace }
├── retry_count: number
├── created_at: timestamp
└── context: { event_data, environment }
```

### Circuit Breaker Pattern

Functions implement graceful degradation:

```python
try:
    # Execute agency workflow
    result = agency.run()
except Exception as e:
    # Log error and send alert
    logger.error(f"Agency execution failed: {str(e)}")
    send_error_alert("daily_execution_failed", str(e))

    # Don't raise - allow function to complete gracefully
    return {"status": "failed", "error": str(e)}
```

## Performance Optimization

### Resource Allocation

```python
# Scheduled function: Heavy agency processing
@scheduler_fn.on_schedule(
    memory=512,           # 512MB for multi-agent execution
    timeout_sec=540,      # 9 minutes for complete workflow
    min_instances=0,      # Cold start acceptable for daily execution
    max_instances=1       # Single instance to prevent conflicts
)

# Event-driven: Lightweight budget monitoring
@firestore_fn.on_document_written(
    memory=256,           # 256MB for budget calculations
    timeout_sec=180,      # 3 minutes for Slack notifications
    min_instances=0,      # Scale to zero when inactive
    max_instances=10      # Auto-scale for concurrent transcripts
)
```

### Cold Start Optimization

```python
# Initialize expensive resources globally
agency = None
config = None

def initialize_resources():
    """Initialize agency and configuration at startup."""
    global agency, config
    if not agency:
        config = load_app_config()
        agency = AutopilootAgency(config=config)
```

## Security & Compliance

### Service Account Permissions

```bash
# Required IAM roles for Firebase Functions service account
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:functions@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/datastore.user"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:functions@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/cloudscheduler.admin"
```

### Firestore Security Rules

```javascript
// firestore.rules - Admin-only access
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read, write: if false;  // Server-only via Admin SDK
    }
  }
}
```

### Environment Variable Security

```bash
# Sensitive variables stored as Firebase config
firebase functions:config:set openai.api_key="sk-your-key"
firebase functions:config:set assemblyai.api_key="your-key"
firebase functions:config:set slack.bot_token="xoxb-your-token"

# Access in function code
import functions from firebase-functions
const openai_key = functions.config().openai.api_key
```

## Troubleshooting

### Common Issues

1. **Function Deployment Fails**

   ```bash
   # Check Python version
   python3 --version  # Must be 3.11+

   # Validate requirements.txt
   cd firebase/functions && pip install -r requirements.txt

   # Deploy with verbose logging
   firebase deploy --only functions --debug
   ```

2. **Scheduled Function Not Executing**

   ```bash
   # Check Cloud Scheduler in GCP Console
   gcloud scheduler jobs list --location=europe-west1

   # Verify timezone configuration
   gcloud scheduler jobs describe daily_scraper --location=europe-west1

   # Manual trigger for testing
   gcloud scheduler jobs run daily_scraper --location=europe-west1
   ```

3. **Event Function Not Triggering**

   ```bash
   # Verify Firestore document writes
   # Check function logs for trigger events
   firebase functions:log --only monitor_transcription_budget

   # Test with manual document write
   # Use Firebase emulator or admin SDK
   ```

4. **Budget Alerts Not Sending**

   ```bash
   # Verify Slack bot token and permissions
   curl -X POST https://slack.com/api/auth.test \
     -H "Authorization: Bearer $SLACK_BOT_TOKEN"

   # Check channel membership
   # Bot must be invited to #ops-autopiloot channel
   ```

5. **Agency Execution Timeout**
   ```bash
   # Monitor function memory usage
   # Consider increasing memory allocation
   # Check for infinite loops in agent workflows
   ```

### Debug Mode

Enable comprehensive logging for troubleshooting:

```python
# In scheduler.py or main.py
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Function-specific debugging
logger = logging.getLogger(__name__)
logger.debug(f"Agency execution starting with config: {config}")
```

### Health Checks

Implement function health monitoring:

```python
@https_fn.on_request()
def health_check(req: https_fn.Request) -> https_fn.Response:
    """Health check endpoint for monitoring."""
    try:
        # Test critical dependencies
        config = load_app_config()
        db = firestore.Client()

        return https_fn.Response(
            json.dumps({"status": "healthy", "timestamp": datetime.utcnow().isoformat()}),
            status=200,
            headers={"Content-Type": "application/json"}
        )
    except Exception as e:
        return https_fn.Response(
            json.dumps({"status": "unhealthy", "error": str(e)}),
            status=500,
            headers={"Content-Type": "application/json"}
        )
```

## Cost Optimization

### Execution Metrics

Monitor function costs and optimize resource usage:

- **Daily Scheduled Function**: ~1 execution/day × 9 minutes × 512MB
- **Budget Monitor**: ~5-10 executions/day × 3 minutes × 256MB
- **Estimated Monthly Cost**: $2-5 USD (varies by execution time)

### Optimization Strategies

1. **Right-size Memory**: Monitor actual usage, reduce if possible
2. **Minimize Cold Starts**: Keep min_instances=0 for cost efficiency
3. **Optimize Execution Time**: Profile agency workflows, optimize bottlenecks
4. **Batch Operations**: Group related tasks to minimize function invocations

---

**Firebase Functions Status**: Production Ready ✅  
**Latest Update**: 2025-09-15  
**Runtime**: Python 3.11  
**Region**: europe-west1  
**Functions**: 2 active (scheduled + event-driven)
