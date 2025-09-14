# 🚀 Firebase Functions Manual Setup Guide

This guide covers the **manual steps** required to deploy and configure Firebase Functions for Autopiloot scheduling.

## 📋 Prerequisites

### 1. **Firebase CLI Installation**
```bash
# Install Firebase CLI globally
npm install -g firebase-tools

# Verify installation
firebase --version
```

### 2. **Authentication**
```bash
# Login to Firebase
firebase login

# Verify you're logged in
firebase projects:list
```

### 3. **Google Cloud SDK (Optional but Recommended)**
```bash
# Install gcloud CLI from: https://cloud.google.com/sdk/docs/install

# Set application default credentials
gcloud auth application-default login
```

## 🔧 Configuration Steps

### 1. **Initialize Firebase Project**

From the repository root (`/Users/maarten/Projects/16 - autopiloot/agents`):

```bash
# Initialize Firebase in the project
firebase init

# Select these options:
# - Functions (Space to select, Enter to confirm)
# - Use an existing project → Select your project
# - Python for Functions language
# - Do NOT overwrite existing files
```

### 2. **Update firebase.json**

Ensure your `firebase.json` includes Functions configuration:

```json
{
  "functions": {
    "source": "autopiloot/firebase/functions",
    "runtime": "python311",
    "ignore": [
      "venv",
      ".git",
      "*.pyc",
      "__pycache__"
    ]
  },
  "firestore": {
    "rules": "firestore.rules",
    "indexes": "firestore.indexes.json"
  }
}
```

### 3. **Set Environment Variables for Functions**

Create `.env` file in `autopiloot/firebase/functions/`:

```bash
cd autopiloot/firebase/functions
cp /Users/maarten/Projects/16\ -\ autopiloot/agents/.env.template .env
# Edit .env with your actual values
```

Or set Firebase environment config:

```bash
# Set environment variables for production
firebase functions:config:set \
  openai.key="YOUR_OPENAI_API_KEY" \
  assemblyai.key="YOUR_ASSEMBLYAI_KEY" \
  youtube.key="YOUR_YOUTUBE_API_KEY" \
  slack.token="YOUR_SLACK_BOT_TOKEN" \
  zep.key="YOUR_ZEP_API_KEY" \
  gcp.project_id="YOUR_PROJECT_ID"

# View current config
firebase functions:config:get
```

### 4. **Service Account Setup**

#### Option A: Using Existing Service Account
```bash
# Set the path to your service account JSON
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

#### Option B: Create New Service Account
```bash
# Create service account in GCP Console
gcloud iam service-accounts create autopiloot-functions \
    --display-name="Autopiloot Functions"

# Grant necessary roles
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:autopiloot-functions@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/datastore.user"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:autopiloot-functions@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/cloudscheduler.admin"

# Download key
gcloud iam service-accounts keys create ./service-account.json \
    --iam-account=autopiloot-functions@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

## 🚀 Deployment

### 1. **Deploy All Functions**

```bash
# From repository root
cd /Users/maarten/Projects/16\ -\ autopiloot/agents

# Deploy all functions
firebase deploy --only functions --project YOUR_PROJECT_ID

# Or deploy specific functions
firebase deploy --only functions:schedule_scraper_daily --project YOUR_PROJECT_ID
firebase deploy --only functions:on_transcription_written --project YOUR_PROJECT_ID
```

### 2. **Verify Deployment**

```bash
# List deployed functions
firebase functions:list --project YOUR_PROJECT_ID

# View function logs
firebase functions:log --project YOUR_PROJECT_ID
```

## 🧪 Testing

### 1. **Local Emulator Testing**

```bash
# Start emulators
firebase emulators:start --only functions,firestore

# The emulator UI will be available at http://localhost:4000
```

### 2. **Manual Trigger Testing**

Test the scraper manually by creating a trigger document:

```javascript
// In Firebase Console or using Admin SDK
db.collection('triggers').doc('scraper_manual').set({
  trigger_time: new Date().toISOString(),
  test: true
});
```

### 3. **Test Schedule (Production)**

Temporarily modify the schedule for immediate testing:

```bash
# Change schedule to run in 2 minutes (for testing only!)
# Edit scheduler.py: schedule="*/2 * * * *"

# Deploy the test schedule
firebase deploy --only functions:schedule_scraper_daily

# After testing, restore to daily schedule: "0 1 * * *"
```

## 📊 Monitoring

### 1. **View Logs**

```bash
# Real-time logs
firebase functions:log --only schedule_scraper_daily

# Filter by function
firebase functions:log --only on_transcription_written

# Last 50 entries
firebase functions:log -n 50
```

### 2. **Google Cloud Console**

1. Go to [Cloud Functions](https://console.cloud.google.com/functions)
2. Select your project
3. Click on function name to see:
   - Metrics (invocations, errors, latency)
   - Logs
   - Source code
   - Triggers

### 3. **Cloud Scheduler (for scheduled functions)**

1. Go to [Cloud Scheduler](https://console.cloud.google.com/cloudscheduler)
2. View scheduled jobs
3. Manually trigger jobs for testing
4. Check execution history

## 🔍 Troubleshooting

### Common Issues and Solutions

#### 1. **Permission Denied Errors**
```bash
# Grant Cloud Functions invoker role
gcloud functions add-iam-policy-binding schedule_scraper_daily \
    --member="allUsers" \
    --role="roles/cloudfunctions.invoker"
```

#### 2. **Module Import Errors**
```bash
# Ensure all dependencies are in requirements.txt
cd autopiloot/firebase/functions
pip install -r requirements.txt
```

#### 3. **Timezone Issues**
- Verify timezone is correctly set to "Europe/Amsterdam"
- Check Cloud Scheduler job configuration in GCP Console

#### 4. **Budget Alerts Not Firing**
- Verify Firestore triggers are deployed
- Check that documents are being written to `transcripts/` collection
- Verify Slack token and channel configuration

### Debug Commands

```bash
# Check function status
gcloud functions describe schedule_scraper_daily

# Test function directly
gcloud functions call schedule_scraper_daily

# View recent errors
gcloud logging read "resource.type=cloud_function" --limit 50
```

## 📝 Maintenance

### Regular Tasks

1. **Weekly**: Check function logs for errors
2. **Monthly**: Review Cloud Scheduler job success rate
3. **Quarterly**: Update dependencies in requirements.txt

### Backup Configuration

```bash
# Export current Functions config
firebase functions:config:get > functions-config-backup.json

# Export Firestore indexes
firebase firestore:indexes > firestore-indexes-backup.json
```

## 🛑 Rollback Procedure

If deployment fails or causes issues:

```bash
# List function versions
gcloud functions list --project YOUR_PROJECT_ID

# Rollback to previous version
firebase functions:delete FUNCTION_NAME --project YOUR_PROJECT_ID
# Then redeploy previous code version
```

## 📞 Support Resources

- [Firebase Functions Documentation](https://firebase.google.com/docs/functions)
- [Cloud Scheduler Documentation](https://cloud.google.com/scheduler/docs)
- [Firebase CLI Reference](https://firebase.google.com/docs/cli)
- [Troubleshooting Guide](https://firebase.google.com/docs/functions/troubleshooting)

## ✅ Deployment Checklist

Before deploying to production:

- [ ] All environment variables configured
- [ ] Service account has necessary permissions
- [ ] `.env` file created with real API keys
- [ ] Tested locally with emulators
- [ ] Verified timezone settings (Europe/Amsterdam)
- [ ] Slack channel configured and bot added
- [ ] Budget thresholds reviewed ($5 daily)
- [ ] Manual trigger tested successfully
- [ ] Monitoring alerts configured
- [ ] Backup of current configuration saved

---

**Note**: After completing these manual steps, your Firebase Functions will be live and running according to the configured schedules. The daily scraper will run at 01:00 AM Amsterdam time, and budget monitoring will trigger automatically on transcript creation.