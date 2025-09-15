# Environment Configuration - Autopiloot Agency

This document explains how to configure environment variables for the Autopiloot Agency.

## Quick Setup

1. **Copy the template:**

   ```bash
   cp ../.env.template .env
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

**Solution**: Copy `../.env.template` to `.env` and fill in the missing values.

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
