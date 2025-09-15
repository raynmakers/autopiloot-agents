# Firebase Functions Deployment Guide

This guide provides step-by-step instructions for deploying the Autopiloot Firebase Functions.

## Prerequisites

### 1. Firebase Project Setup

```bash
# Install Firebase CLI
npm install -g firebase-tools

# Login to Firebase
firebase login

# List available projects
firebase projects:list
```

### 2. Initialize Firebase Project

```bash
# Navigate to project root
cd /Users/maarten/Projects/16\ -\ autopiloot/agents/autopiloot

# Initialize or use existing project
firebase use --add your-project-id

# Or create new project
firebase projects:create your-project-id
```

### 3. Enable Required Services

In the [Firebase Console](https://console.firebase.google.com):

1. Enable **Cloud Functions**
2. Enable **Cloud Firestore**
3. Enable **Cloud Scheduler** (for scheduled functions)

## Environment Configuration

### 1. Set Function Environment Variables

```bash
# Set Slack bot token (required)
firebase functions:config:set slack.bot_token="xoxb-your-slack-bot-token"

# Set Google Application Credentials path (if using service account file)
firebase functions:config:set google.credentials_path="path/to/service-account.json"

# Optional: Set custom daily budget (defaults to $5.00)
firebase functions:config:set budget.daily_usd="5.0"
```

### 2. Service Account Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Navigate to **IAM & Admin > Service Accounts**
3. Create new service account or use existing one
4. Grant permissions:
   - **Firebase Admin SDK Administrator Service Agent**
   - **Cloud Datastore User**
   - **Cloud Scheduler Admin** (for scheduled functions)
5. Generate and download JSON key file
6. Set `GOOGLE_APPLICATION_CREDENTIALS` environment variable

### 3. Local Environment File

Create `.env` file for local development:

```bash
# Copy example file
cp .env.example .env

# Edit with your actual values
nano .env
```

## Deployment Steps

### 1. Deploy Firestore Configuration

```bash
# Deploy security rules and indexes
firebase deploy --only firestore:rules,firestore:indexes
```

### 2. Deploy Functions

```bash
# Deploy all functions
firebase deploy --only functions

# Or deploy specific functions
firebase deploy --only functions:schedule_scraper_daily
firebase deploy --only functions:on_transcription_written
```

### 3. Verify Deployment

```bash
# Check function status
firebase functions:log

# Test scheduled function (manual trigger)
# Note: This will create a test job in Firestore
gcloud functions call schedule_scraper_daily --region=europe-west1
```

## Testing Deployed Functions

### 1. Test Scheduled Function

```bash
# View Cloud Scheduler jobs
gcloud scheduler jobs list

# Manually trigger the scheduled job
gcloud scheduler jobs run firebase-schedule-schedule_scraper_daily-europe-west1

# Check function logs
firebase functions:log --only schedule_scraper_daily
```

### 2. Test Event-Driven Function

```bash
# Create test transcript document in Firestore
# This can be done via Firebase Console or admin SDK

# Example using Firebase Console:
# 1. Go to Firestore in Firebase Console
# 2. Create document: transcripts/test-video-123
# 3. Add fields:
#    - created_at: "2025-01-27T10:00:00Z"
#    - costs: { transcription_usd: 4.5 }
# 4. Save document
# 5. Check function logs for budget alert

firebase functions:log --only on_transcription_written
```

### 3. Monitor Slack Notifications

Check the `#ops-autopiloot` Slack channel for:

- Daily scraper job creation messages
- Budget threshold alerts
- Error notifications

## Troubleshooting

### Common Issues

#### 1. Function Deployment Fails

```bash
# Check Node.js version (if using Node functions)
node --version

# Check Python version (should be 3.11)
python3 --version

# Verify requirements.txt
cat firebase/functions/requirements.txt

# Check for syntax errors
python3 -m py_compile firebase/functions/main.py
```

#### 2. Scheduled Function Not Running

```bash
# Check Cloud Scheduler status
gcloud scheduler jobs describe firebase-schedule-schedule_scraper_daily-europe-west1

# Verify timezone configuration
gcloud scheduler jobs describe firebase-schedule-schedule_scraper_daily-europe-west1 --format="value(schedule,timeZone)"

# Check function permissions
gcloud functions get-iam-policy schedule_scraper_daily --region=europe-west1
```

#### 3. Event Function Not Triggering

```bash
# Verify Firestore trigger configuration
gcloud functions describe on_transcription_written --region=europe-west1

# Check Firestore document path matches trigger
# Trigger: transcripts/{video_id}
# Document path should be: transcripts/some-video-id

# Check function logs for errors
firebase functions:log --only on_transcription_written --lines 50
```

#### 4. Slack Notifications Not Working

```bash
# Verify Slack bot token configuration
firebase functions:config:get

# Test Slack bot permissions in your workspace
# Bot needs permission to post in #ops-autopiloot channel

# Check function logs for Slack API errors
firebase functions:log | grep -i slack
```

### Debug Mode

Enable detailed logging by updating main.py:

```python
# Change logging level to DEBUG
logging.basicConfig(level=logging.DEBUG)
```

Then redeploy:

```bash
firebase deploy --only functions
```

## Monitoring & Maintenance

### Function Metrics

- View in [Google Cloud Console > Cloud Functions](https://console.cloud.google.com/functions)
- Monitor execution time, memory usage, error rates
- Set up alerting for function failures

### Cost Monitoring

- Functions trigger budget alerts at 80% of daily $5 limit
- View detailed costs in `costs_daily` Firestore collection
- Monitor Firebase Functions usage in billing console

### Logs Analysis

```bash
# Real-time logs
firebase functions:log --only schedule_scraper_daily --follow

# Filter by time
firebase functions:log --since 2h

# Export logs for analysis
gcloud logging read "resource.type=cloud_function" --format=json > function_logs.json
```

## Security Considerations

- Functions use Firebase Admin SDK with elevated privileges
- Firestore rules deny all client access (server-only)
- Environment variables store sensitive API keys
- Audit logs track all function executions in `audit_logs` collection

## Performance Configuration

Current settings (can be adjusted in main.py):

- **Memory**: 256MB per function
- **Timeout**: 300s for scheduled, 180s for event-driven
- **Region**: europe-west1
- **Concurrency**: Auto-scaling

To modify, update the decorator parameters:

```python
@scheduler_fn.on_schedule(
    memory=options.MemoryOption.MB_512,  # Increase memory
    timeout_sec=600                       # Increase timeout
)
```
