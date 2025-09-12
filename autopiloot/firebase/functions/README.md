# Firebase Functions for Autopiloot

This directory contains Firebase Functions v2 for the Autopiloot project, implementing scheduled and event-driven automation.

## Functions

### 1. `schedule_scraper_daily`

- **Type**: Scheduled Function
- **Schedule**: Daily at 01:00 Europe/Amsterdam (`0 1 * * *`)
- **Purpose**: Triggers the scraper agent to discover new YouTube videos
- **Output**: Creates job documents in `jobs/scraper/daily/{job_id}`

### 2. `on_transcription_written`

- **Type**: Event-driven Function
- **Trigger**: Firestore document writes to `transcripts/{video_id}`
- **Purpose**: Monitors daily transcription budget and sends Slack alerts at 80% threshold
- **Output**: Updates `costs_daily/{date}` and sends Slack notifications

## Configuration

### Environment Variables

Required environment variables (set in Firebase Functions config):

```bash
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token

# Optional: Override default budget (defaults to $5.00)
DAILY_BUDGET_USD=5.0
```

### Firebase Project Setup

1. Ensure your Firebase project has Firestore and Functions enabled
2. Set up service account with appropriate permissions
3. Configure Firestore security rules (server-only access)

## Deployment

### Prerequisites

```bash
# Install Firebase CLI
npm install -g firebase-tools

# Login and select project
firebase login
firebase use your-project-id
```

### Deploy Functions

```bash
# From the agents/autopiloot directory
cd /Users/maarten/Projects/16 - autopiloot/agents/autopiloot

# Deploy all functions
firebase deploy --only functions

# Deploy specific function
firebase deploy --only functions:schedule_scraper_daily
firebase deploy --only functions:on_transcription_written
```

### Deploy Firestore Configuration

```bash
# Deploy security rules and indexes
firebase deploy --only firestore:rules
firebase deploy --only firestore:indexes
```

## Local Development

### Start Emulators

```bash
# Start Functions and Firestore emulators
firebase emulators:start --only functions,firestore

# Access emulator UI at http://localhost:4000
```

### Test Functions Locally

```bash
# Trigger scheduled function manually
curl -X POST http://localhost:5001/your-project-id/europe-west1/schedule_scraper_daily

# Create test transcript document to trigger event function
# Use the Firestore emulator UI or admin SDK
```

## Monitoring

### Logs

```bash
# View function logs
firebase functions:log

# Follow real-time logs
firebase functions:log --only schedule_scraper_daily

# View specific function logs
firebase functions:log --only on_transcription_written
```

### Slack Notifications

Functions send alerts to the `#ops-autopiloot` Slack channel for:

- Successful daily scraper job creation
- Budget threshold exceeded (80% of daily limit)
- Function execution errors

### Firestore Collections Used

- `jobs/scraper/daily/{job_id}` - Scraper job queue
- `transcripts/{video_id}` - Transcript documents (trigger)
- `costs_daily/{YYYY-MM-DD}` - Daily cost tracking
- `videos/{video_id}` - Video metadata

## Troubleshooting

### Common Issues

1. **Function deployment fails**

   - Check Python version (requires Python 3.11)
   - Verify all dependencies in requirements.txt
   - Ensure Firebase project has Functions enabled

2. **Scheduled function not running**

   - Verify timezone configuration
   - Check Cloud Scheduler in Google Cloud Console
   - Review function logs for errors

3. **Event function not triggering**

   - Confirm Firestore trigger path matches document writes
   - Check Firestore security rules
   - Verify document structure includes required fields

4. **Slack alerts not sending**
   - Verify SLACK_BOT_TOKEN environment variable
   - Check bot permissions for target channel
   - Review function execution logs

### Debug Mode

Enable detailed logging by setting log level in function code:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Security

- Functions use Firebase Admin SDK with elevated privileges
- Firestore rules deny all client access (server-only)
- Sensitive data (API keys) stored in environment variables
- All costs and job data tracked in audit logs

## Performance

- **Memory**: 256MB per function
- **Timeout**: 300s for scheduled, 180s for event-driven
- **Region**: europe-west1 (matches Amsterdam timezone)
- **Concurrency**: Automatic scaling based on demand
