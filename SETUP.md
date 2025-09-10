# Detailed Setup Instructions

Complete guide for setting up and running the Autopiloot Agents development environment.

## Prerequisites

- [Node.js](https://nodejs.org/) (v18 or later)
- [Firebase CLI](https://firebase.google.com/docs/cli)
- [Python 3.11](https://www.python.org/downloads/) (for Firebase Functions)

## Installation

### 1. Install Firebase CLI

```bash
npm install -g firebase-tools
```

### 2. Login to Firebase

```bash
firebase login
```

This will open a browser window for authentication. Follow the prompts to complete the login.

### 3. Install Project Dependencies

If you have Python Firebase Functions:

```bash
# Create requirements.txt if it doesn't exist
touch requirements.txt

# Install Python dependencies
pip install -r requirements.txt
```

## Firebase Emulator Setup

### Start All Emulators

```bash
firebase emulators:start
```

This command starts all configured emulators:

- **Functions Emulator**: http://localhost:5001
- **Firestore Emulator**: http://localhost:8080
- **Storage Emulator**: http://localhost:9199
- **Emulator UI**: http://localhost:4001

### Start Specific Emulators

```bash
# Start only Firestore and Functions
firebase emulators:start --only firestore,functions

# Start only the Emulator UI
firebase emulators:start --only ui

# Start with debug logging
firebase emulators:start --debug
```

### Emulator Configuration

The emulator ports are configured in `firebase.json`:

```json
{
  "emulators": {
    "functions": { "port": 5001 },
    "firestore": { "port": 8080 },
    "storage": { "port": 9199 },
    "ui": { "enabled": true, "port": 4001 }
  }
}
```

## Development Workflow

### 1. Start Development Environment

```bash
# Start all emulators
firebase emulators:start

# In another terminal, start your development server
# (if you have a frontend application)
```

### 2. Access Emulator UI

Open http://localhost:4001 in your browser to:

- View and manage Firestore data
- Monitor function executions
- Check storage files
- View emulator logs

### 3. Develop and Test

- **Firebase Functions**: Place Python functions in the root directory
- **Firestore**: Use the emulator UI or Firebase SDK to interact with data
- **Storage**: Upload and manage files through the emulator UI

### 4. Deploy to Production

```bash
# Deploy everything
firebase deploy

# Deploy specific services
firebase deploy --only functions
firebase deploy --only firestore:rules
firebase deploy --only storage
```

## Firebase Functions Development

### Python Functions Structure

```
agents/
├── main.py              # Main functions file
├── requirements.txt     # Python dependencies
└── firebase.json        # Firebase configuration
```

### Example Function

```python
# main.py
from firebase_functions import https_fn
from firebase_admin import initialize_app

initialize_app()

@https_fn.on_request()
def hello_world(req: https_fn.Request) -> https_fn.Response:
    return https_fn.Response("Hello from Firebase Functions!")
```

### Testing Functions Locally

```bash
# Start emulators
firebase emulators:start

# Test function endpoint
curl http://localhost:5001/your-project-id/us-central1/hello_world
```

## Security Rules

### Firestore Rules

Edit `firestore.rules` to control data access:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Allow read/write access to authenticated users
    match /{document=**} {
      allow read, write: if request.auth != null;
    }
  }
}
```

### Storage Rules

Edit `storage.rules` to control file access:

```javascript
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /{allPaths=**} {
      allow read, write: if request.auth != null;
    }
  }
}
```

## Useful Commands

### Emulator Management

```bash
# Start emulators with data import
firebase emulators:start --import=./emulator-data

# Start emulators with data export on exit
firebase emulators:start --export-on-exit

# Clear all emulator data
firebase emulators:start --import=./empty-data --export-on-exit
```

### Deployment Commands

```bash
# Deploy with specific project
firebase deploy --project your-project-id

# Deploy only functions
firebase deploy --only functions

# Deploy only Firestore rules
firebase deploy --only firestore:rules

# Deploy only Storage rules
firebase deploy --only storage

# Deploy with force (overwrite existing)
firebase deploy --force
```

### Project Management

```bash
# List all projects
firebase projects:list

# Switch project
firebase use your-project-id

# View current project
firebase projects:list --filter="projectId:your-project-id"
```

## Troubleshooting

### Common Issues

#### Port Conflicts

If you get port conflicts:

```bash
# Check what's using the port
lsof -i :5001  # For functions port
lsof -i :8080  # For Firestore port

# Kill the process or change ports in firebase.json
```

#### Authentication Issues

```bash
# Re-authenticate
firebase logout
firebase login

# Check current user
firebase auth:export --help
```

#### Python Functions Not Working

```bash
# Verify Python version
python3 --version  # Should be 3.11+

# Install dependencies
pip install -r requirements.txt

# Check Firebase Functions Python SDK
pip install firebase-functions[framework]
```

#### Emulator Data Issues

```bash
# Clear emulator data
rm -rf .firebase/emulators

# Start fresh
firebase emulators:start
```

### Debug Mode

```bash
# Start with debug logging
firebase emulators:start --debug

# View detailed logs
firebase emulators:start --debug --verbose
```

## Environment Variables

### Local Development

Create a `.env` file for local development:

```bash
# .env
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
```

### Production

Set environment variables in Firebase Console:

1. Go to Firebase Console → Functions → Configuration
2. Add environment variables
3. Redeploy functions

## Best Practices

### Development

1. **Always use emulators** for local development
2. **Test functions locally** before deploying
3. **Use version control** for security rules
4. **Monitor emulator logs** for debugging

### Security

1. **Review security rules** regularly
2. **Test rules** with the emulator UI
3. **Use least privilege** principle
4. **Validate input** in functions

### Performance

1. **Optimize Firestore queries** (use indexes)
2. **Minimize function cold starts**
3. **Use appropriate data types**
4. **Monitor usage** in Firebase Console

## Resources

- [Firebase Documentation](https://firebase.google.com/docs)
- [Firebase Emulator Suite](https://firebase.google.com/docs/emulator-suite)
- [Firebase Functions Python](https://firebase.google.com/docs/functions/python)
- [Firestore Security Rules](https://firebase.google.com/docs/firestore/security/get-started)
- [Firebase CLI Reference](https://firebase.google.com/docs/cli)
