# Autopiloot Agents

AI agent development tools and Firebase configuration for the Autopiloot project.

## Quick Start

1. **Install Firebase CLI:**

   ```bash
   npm install -g firebase-tools
   firebase login
   ```

2. **Start Firebase Emulators:**

   ```bash
   firebase emulators:start
   ```

3. **Access Emulator UI:** http://localhost:4001

## Repository Structure

```
agents/
├── .cursor/rules/       # AI agent rules and ADRs
├── tasks/              # Task templates
├── firebase.json       # Firebase configuration
├── firestore.rules     # Firestore security rules
└── storage.rules       # Storage security rules
```

## Architecture

Event-driven broker architecture using Firestore as both data store and event broker. See [Architecture Decision Records](.cursor/rules/ADR.mdc) for details.

## Development

- **Emulators**: Functions (5001), Firestore (8080), Storage (9199), UI (4001)
- **Functions**: Python 3.11 Firebase Functions
- **Real-time**: Firestore listeners for agent data updates

## Documentation

- **[Detailed Setup Instructions](SETUP.md)** - Complete installation and configuration guide
- **[Architecture Decisions](.cursor/rules/ADR.mdc)** - Technical architecture documentation
- **[Task Templates](tasks/)** - Agent development templates

## Quick Commands

```bash
# Start emulators
firebase emulators:start

# Deploy to production
firebase deploy

# Deploy specific services
firebase deploy --only functions,firestore:rules
```
