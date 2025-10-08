# Firebase Storage Setup for Autopiloot

## Automatic File Deletion (24-hour TTL)

To prevent storage costs from accumulating, configure Firebase Storage to automatically delete temporary transcription audio files after 24 hours.

### Option 1: Using gcloud CLI (Recommended)

1. Install gcloud CLI if not already installed:
   ```bash
   # macOS
   brew install google-cloud-sdk

   # Or download from: https://cloud.google.com/sdk/docs/install
   ```

2. Authenticate with your Google Cloud project:
   ```bash
   gcloud auth login
   gcloud config set project autopiloot-dev
   ```

3. Apply the lifecycle policy:
   ```bash
   gsutil lifecycle set config/firebase-storage-lifecycle.json gs://autopiloot-dev.firebasestorage.app
   ```

4. Verify the policy was applied:
   ```bash
   gsutil lifecycle get gs://autopiloot-dev.firebasestorage.app
   ```

### Option 2: Using Firebase Console

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Select your project: `autopiloot-dev`
3. Navigate to **Storage** in the left sidebar
4. Click on **Files** tab
5. Click the **Rules** tab
6. Add a lifecycle rule:
   - **Action**: Delete
   - **Condition**: Age = 1 day
   - **Prefix**: `tmp/transcription/`

### What This Does

- **Automatically deletes files** in `tmp/transcription/` folder after 24 hours
- **Prevents storage costs** from accumulating if CleanupTranscriptionAudio tool fails
- **Runs daily** - Firebase Storage checks all files once per day
- **Safe cleanup** - Only affects temporary transcription files, not transcripts or summaries

### File Metadata

Each uploaded audio file includes metadata:
- `expires_at`: ISO timestamp of 24-hour expiration
- `video_id`: YouTube video ID for tracking
- `purpose`: "temporary_transcription_audio"

This metadata helps with manual cleanup if needed, but automatic deletion is based on file age (24 hours from creation).

### Verification

After applying the policy, you can verify it's working:

```bash
# List files in tmp/transcription/ folder
gsutil ls gs://autopiloot-dev.firebasestorage.app/tmp/transcription/

# Check lifecycle policy
gsutil lifecycle get gs://autopiloot-dev.firebasestorage.app
```

Files older than 24 hours should be automatically deleted during the daily cleanup cycle.

### Manual Cleanup (if needed)

If you need to manually delete old files:

```bash
# Delete all files in tmp/transcription/ folder
gsutil -m rm -r gs://autopiloot-dev.firebasestorage.app/tmp/transcription/**
```

Or use the CleanupTranscriptionAudio tool from the transcriber agent.
