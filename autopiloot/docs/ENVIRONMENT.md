# Environment Configuration - Autopiloot Agency

This document explains how to configure environment variables for the Autopiloot Agency.

## Quick Setup

1. **Copy the template:**

   ```bash
   cp .env.template .env
   ```

2. **Fill in your API keys and credentials in `.env`**

3. **Verify configuration:**
   ```bash
   python config/env_loader.py
   ```

## Required Environment Variables

### API Keys

- **`OPENAI_API_KEY`**: OpenAI API key for LLM operations (GPT-4.1)
- **`ASSEMBLYAI_API_KEY`**: AssemblyAI API key for audio transcription
- **`YOUTUBE_API_KEY`**: YouTube Data API v3 key for video discovery
- **`SLACK_BOT_TOKEN`**: Slack bot token for notifications (starts with `xoxb-`)
- **`ZEP_API_KEY`**: Zep API key for GraphRAG storage

### Google Services

- **`GCP_PROJECT_ID`**: Google Cloud Project ID for Firestore and other GCP services
- **`GOOGLE_APPLICATION_CREDENTIALS`**: Path to Google service account JSON file
- **`GOOGLE_DRIVE_FOLDER_ID_TRANSCRIPTS`**: Google Drive folder ID for transcript storage
- **`GOOGLE_DRIVE_FOLDER_ID_SUMMARIES`**: Google Drive folder ID for summary storage

### Optional Variables

- **`SLACK_SIGNING_SECRET`**: Slack signing secret for webhook verification (optional)
- **`LANGFUSE_PUBLIC_KEY`**: Langfuse public key for LLM observability (optional)
- **`LANGFUSE_SECRET_KEY`**: Langfuse secret key for LLM observability (optional)
- **`LANGFUSE_HOST`**: Langfuse host URL (default: https://cloud.langfuse.com)
- **`ZEP_COLLECTION`**: Zep collection name (default: autopiloot_guidelines)
- **`TIMEZONE`**: Timezone for scheduling (default: Europe/Amsterdam)

## How to Get API Keys

### OpenAI

1. Visit [OpenAI API](https://platform.openai.com/api-keys)
2. Create a new API key
3. Copy the key (starts with `sk-`)

### AssemblyAI

1. Visit [AssemblyAI](https://www.assemblyai.com/)
2. Sign up and get your API key from the dashboard

### YouTube Data API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Enable YouTube Data API v3
3. Create credentials (API key)

### Slack

1. Create a Slack app at [api.slack.com](https://api.slack.com/apps)
2. Add the bot token OAuth scope
3. Install the app to your workspace
4. Copy the bot token (starts with `xoxb-`)

### Google Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Enable Drive API and Sheets API
3. Create a service account
4. Download the JSON credentials file
5. Set the file path in `GOOGLE_APPLICATION_CREDENTIALS`

### Zep

1. Visit [Zep Cloud](https://www.getzep.com/)
2. Sign up and get your API key from the dashboard

## Google Cloud Service Account Setup

### Creating a Service Account

1. **Go to Google Cloud Console**
   - Visit [Google Cloud Console](https://console.cloud.google.com/)
   - Select or create a project

2. **Enable Required APIs**
   ```bash
   # Enable required Google APIs
   gcloud services enable firestore.googleapis.com
   gcloud services enable drive.googleapis.com
   gcloud services enable sheets.googleapis.com
   ```

3. **Create Service Account**
   - Go to **IAM & Admin > Service Accounts**
   - Click **Create Service Account**
   - Name: `autopiloot-agency`
   - Description: `Service account for Autopiloot Agency operations`

4. **Assign Minimal Required Roles**
   ```
   - Cloud Datastore User (for Firestore access)
   - Storage Object Admin (for file uploads, if using Cloud Storage)
   ```

5. **Create and Download Key**
   - Click on the created service account
   - Go to **Keys** tab
   - Click **Add Key > Create New Key**
   - Choose **JSON** format
   - Download and save securely

6. **Set Environment Variable**
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
   ```

### Google Drive Folder Setup

1. **Create Folders**
   - Create two folders in Google Drive:
     - `Autopiloot Transcripts`
     - `Autopiloot Summaries`

2. **Share Folders with Service Account**
   - Right-click each folder > Share
   - Add the service account email (e.g., `autopiloot-agency@your-project.iam.gserviceaccount.com`)
   - Give **Editor** permissions

3. **Get Folder IDs**
   - Open each folder in Google Drive
   - Copy the folder ID from the URL: `https://drive.google.com/drive/folders/FOLDER_ID_HERE`
   - Set in `.env`:
     ```
     GOOGLE_DRIVE_FOLDER_ID_TRANSCRIPTS=your_transcript_folder_id
     GOOGLE_DRIVE_FOLDER_ID_SUMMARIES=your_summary_folder_id
     ```

### Firestore Database Setup

1. **Create Firestore Database**
   - Go to **Firestore > Create Database**
   - Choose **Native Mode**
   - Select region (recommend same as your application)

2. **Configure Security Rules** (see FIREBASE_IMPLEMENTATION.md for details)
   ```javascript
   rules_version = '2';
   service cloud.firestore {
     match /databases/{database}/documents {
       // Allow service account access
       match /{document=**} {
         allow read, write: if request.auth != null;
       }
     }
   }
   ```

### Security Best Practices

#### Service Account Permissions
- **Principle of Least Privilege**: Only grant minimum required permissions
- **Regular Rotation**: Rotate service account keys every 90 days
- **Monitoring**: Enable audit logging for service account usage

#### Recommended IAM Roles
```
# Minimal permissions for Autopiloot Agency
- roles/datastore.user          # Firestore read/write
- roles/storage.objectAdmin     # Cloud Storage (if used)
- roles/drive.file             # Google Drive access to created files only
```

#### Key Management
- **Secure Storage**: Store keys in secure credential management systems
- **Environment Isolation**: Use different service accounts for dev/staging/prod
- **Access Monitoring**: Regularly review service account usage logs

### Firestore Collection Structure

The service account needs access to these collections:
```
/videos/{video_id}                    # Video metadata and processing status
/transcripts/{video_id}               # Transcript content and metadata
/summaries/{video_id}                 # Generated summaries
/jobs/transcription/{job_id}          # Transcription job tracking
/jobs/summarization/{job_id}          # Summarization job tracking
/audit_logs/{log_id}                  # Audit trail for compliance
/jobs_deadletter/{job_id}             # Failed jobs requiring attention
/alert_throttling/{alert_key}         # Alert throttling state
/costs_daily/{date}                   # Daily cost tracking
```

### Troubleshooting Service Account Issues

#### Authentication Errors
```bash
# Verify service account key
gcloud auth activate-service-account --key-file=/path/to/key.json

# Test Firestore access
python -c "
from google.cloud import firestore
db = firestore.Client()
collections = list(db.collections())
print(f'✅ Firestore accessible: {len(collections)} collections')
"
```

#### Permission Errors
```bash
# Check service account permissions
gcloud projects get-iam-policy YOUR_PROJECT_ID \
  --filter="bindings.members:serviceAccount:autopiloot-agency@YOUR_PROJECT_ID.iam.gserviceaccount.com"
```

#### Drive Access Errors
- Verify folder sharing with service account email
- Check folder IDs are correct in environment variables
- Ensure service account has Editor permissions on folders

## Testing Environment

Run the environment loader to verify all variables are set correctly:

```bash
# Activate virtual environment
source venv/bin/activate

# Test environment loading
python config/env_loader.py
```

Expected output:

```
✅ All required environment variables are present:
  - Timezone: Europe/Amsterdam
  - Zep Collection: autopiloot_guidelines
  - OPENAI API key: ✅ Set
  - ASSEMBLYAI API key: ✅ Set
  - YOUTUBE API key: ✅ Set
  - ZEP API key: ✅ Set
  - SLACK API key: ✅ Set
  - Google credentials: ✅ /path/to/service-account.json

🎉 Environment configuration is valid!
```

## Security Notes

- **Never commit `.env` files** - they contain secrets
- The `.env` file is already in `.gitignore`
- Store credentials securely in production
- Rotate API keys regularly
- Use least-privilege access for service accounts

## Troubleshooting

### Missing Environment Variable

```
❌ Environment validation failed:
Missing required environment variables:
  - OPENAI_API_KEY: OpenAI API key for LLM operations
```

**Solution**: Copy `.env.template` to `.env` and fill in the missing values.

### File Not Found

```
❌ Google credentials file not found: /path/to/credentials.json
```

**Solution**: Verify the file path in `GOOGLE_APPLICATION_CREDENTIALS` is correct.

### Invalid API Key

Check your API keys are correct and have proper permissions:

- OpenAI: Must have access to GPT-4 models
- AssemblyAI: Must have transcription quota
- YouTube: Must have quota for Data API v3
- Slack: Must have `chat:write` scope
- Google: Service account must have Drive and Sheets API access

## Dependencies

The environment loader requires these packages (already in requirements.txt):

- `python-dotenv` - For loading .env files
- `pathlib` - For file path handling

All dependencies can be installed with:

```bash
pip install -r requirements.txt
```
